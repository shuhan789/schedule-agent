"""结果对账（Guard）。

模型通过 submit_report 给出结论，但“保存成功没有”“审核过没过”这类事实以工具记录为准：
- 草稿保存状态只认 save_draft 的真实返回，模型声称成功而工具失败时更正，并记入 guard_notes；
- 审核结论只认最后一次 check_rules 的结果；
- 总结里出现“已发布 / 已上线”等越权表述会被替换并记录；
- 循环异常结束（步数上限等）时，也能根据工具记录给出每个素材的真实状态。
guard_notes 不为空，说明模型的报告有误，评估时会单独统计。
"""
from __future__ import annotations

import re

from .store import DraftStore

PUBLISH_CLAIM = re.compile(r"(?<![未不没非无])(已经?发布|已上线|发布成功|已推送上线)")

REVIEW_MAP = {"pass": "approved", "needs_info": "needs_info", "block": "blocked",
              "needs_verification": "needs_verification"}


def _last(log: list[dict], tool: str, material_id: str, ok_only: bool = False) -> dict | None:
    for e in reversed(log):
        if e["tool"] == tool and e["args"].get("material_id") == material_id:
            if ok_only and not e["result"].get("ok"):
                continue
            return e
    return None


def reconcile(request: dict, model_report: dict | None, log: list[dict], store: DraftStore,
              termination: dict) -> dict:
    notes: list[str] = []
    model_items = {}
    if model_report:
        for it in model_report.get("items", []) or []:
            if isinstance(it, dict) and it.get("material_id"):
                model_items[it["material_id"]] = it

    out_items = []
    for req in request["items"]:
        mid = req["material_id"]
        mi = model_items.get(mid, {})
        if model_report is not None and not mi:
            notes.append(f"{mid}: 模型报告中缺少该素材，按工具记录补全")

        # ---- 审核结论：以最后一次成功的 check_rules 为准 ----
        chk = _last(log, "check_rules", mid, ok_only=True)
        if chk:
            verdict = chk["result"]["verdict"]
            review = REVIEW_MAP[verdict]
            risks = [h["message"] for h in chk["result"]["hits"]]
        else:
            review, risks = "not_checked", []
        if mi.get("review_status") and mi["review_status"] != review:
            notes.append(f"{mid}: 模型报告审核结论为 {mi['review_status']}，工具记录为 {review}，已按工具记录更正")
        if not risks and mi.get("risk_reasons"):
            risks = list(mi["risk_reasons"])

        # ---- 草稿：以最后一次 save_draft 的真实返回为准 ----
        sv = _last(log, "save_draft", mid)
        existing = store.get(mid, req["channel"], req["date"])
        if sv and sv["result"].get("ok"):
            d = sv["result"]["draft"]
            draft = {"saved": True, "action": sv["result"]["action"], "draft_id": d["draft_id"],
                     "time": d["time"], "status": d["status"], "version": d["version"]}
        elif sv:
            draft = {"saved": False, "action": "failed", "error_code": sv["result"].get("error_code"),
                     "error": sv["result"].get("message")}
            if existing:
                draft["existing_draft"] = {"draft_id": existing["draft_id"], "time": existing["time"],
                                           "status": existing["status"]}
        else:
            draft = {"saved": False, "action": "not_attempted"}
            if existing:
                draft["existing_draft"] = {"draft_id": existing["draft_id"], "time": existing["time"],
                                           "status": existing["status"]}
        if mi.get("draft_saved") is True and not draft["saved"]:
            notes.append(f"{mid}: 模型声称草稿已保存，但工具记录为 {draft['action']}"
                         f"{'/' + str(draft.get('error_code')) if draft.get('error_code') else ''}，已更正为未保存")
        if mi.get("draft_id") and draft["saved"] and mi["draft_id"] != draft["draft_id"]:
            notes.append(f"{mid}: 模型报告的 draft_id 与工具返回不一致，已更正")

        # ---- 时段与确认 ----
        requested = req.get("preferred_time")
        if draft["saved"]:
            suggested = draft["time"]
            saved_items = sv["result"]["draft"].get("confirmation_items", [])
            needs_conf = bool(sv["result"]["draft"]["needs_confirmation"])
        else:
            suggested = mi.get("suggested_time") or None
            saved_items = []
            needs_conf = bool(mi.get("needs_confirmation")) or bool(suggested and requested and suggested != requested)
        pending = list(dict.fromkeys(list(saved_items) + list(mi.get("pending_confirmations") or [])))
        if needs_conf and not pending:
            pending = [f"原定 {requested}，建议 {suggested}，需用户确认"]

        # ---- 最终状态 ----
        if review == "blocked":
            state = "blocked"
        elif review == "needs_info":
            state = "needs_info"
        elif draft["saved"]:
            state = "draft_saved_pending_confirmation" if needs_conf else "draft_saved"
        elif review == "approved" and draft["action"] == "failed" and draft.get("error_code") not in (
                "HARD_CONSTRAINT_VIOLATION",):
            state = "save_failed"
        elif review == "approved" and needs_conf:
            state = "awaiting_confirmation"
        else:
            state = "unresolved"

        out_items.append({
            "material_id": mid, "channel": req["channel"], "date": req["date"],
            "requested_time": requested, "time_flexibility": req.get("time_flexibility", "flexible"),
            "review_status": review, "risk_reasons": risks,
            "suggested_time": suggested, "needs_confirmation": needs_conf,
            "pending_confirmations": pending, "draft": draft, "final_state": state,
            "next_step": mi.get("next_step", ""),
        })

    summary = (model_report or {}).get("summary", "")
    if PUBLISH_CLAIM.search(summary or ""):
        notes.append("总结中出现“已发布/已上线”等越权表述，已替换")
        summary = PUBLISH_CLAIM.sub("[已更正：仅保存草稿，未发布]", summary)
    for it in out_items:
        if it["next_step"] and PUBLISH_CLAIM.search(it["next_step"]):
            notes.append(f"{it['material_id']}: next_step 出现越权表述，已替换")
            it["next_step"] = PUBLISH_CLAIM.sub("[已更正：仅保存草稿，未发布]", it["next_step"])

    states = [it["final_state"] for it in out_items]
    if not termination.get("submitted"):
        task_status = "incomplete"
    elif any(s in ("save_failed", "unresolved") for s in states):
        task_status = "partial_failed"
    elif all(s == "draft_saved" for s in states):
        task_status = "completed"
    else:
        task_status = "needs_user_action"

    return {
        "request_id": request.get("request_id"),
        "task_status": task_status,
        "status_reason": termination.get("reason", ""),
        "published": False,  # 系统没有发布能力，恒为 False
        "items": out_items,
        "summary": summary,
        "guard_notes": notes,
    }
