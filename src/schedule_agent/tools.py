"""业务工具（本地函数）。

设计原则：模型负责“选哪个动作”，工具负责“硬约束”。
- 没有发布工具，只有 save_draft，从能力上杜绝越权发布。
- save_draft 在写入前做校验：日期不可改、未通过审核不可存、时段冲突不可存、
  改了用户要求的时间必须标记待确认、固定时间不可改。模型即使决策出错也写不进去。
- 每次调用都返回 {ok: bool, ...}；失败时带 error_code 和 retryable，供模型决定下一步。
- 支持故障注入（FaultPlan），用于验收“工具失败 / 保存失败”。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .store import DraftStore, World


# ---------------------------------------------------------------- 故障注入
@dataclass
class FaultPlan:
    """spec 形如 {"save_draft": {"mode": "always"} } 或 {"query_slots": {"mode": "first_n", "n": 1}}"""
    spec: dict = field(default_factory=dict)
    calls: dict = field(default_factory=dict)

    DEFAULT_CODES = {
        "save_draft": "STORAGE_UNAVAILABLE",
        "query_slots": "SCHEDULE_SERVICE_TIMEOUT",
        "read_material": "MATERIAL_SERVICE_TIMEOUT",
        "check_rules": "RULE_ENGINE_TIMEOUT",
        "lookup_license": "LICENSE_DB_TIMEOUT",
    }

    def check(self, tool: str) -> str | None:
        n_call = self.calls.get(tool, 0) + 1
        self.calls[tool] = n_call
        rule = self.spec.get(tool)
        if not rule:
            return None
        mode = rule.get("mode", "always")
        if mode == "always" or (mode == "first_n" and n_call <= int(rule.get("n", 1))):
            return rule.get("error_code", self.DEFAULT_CODES.get(tool, "TOOL_ERROR"))
        return None


def _err(code: str, message: str, retryable: bool = False, **extra) -> dict:
    return {"ok": False, "error_code": code, "message": message, "retryable": retryable, **extra}


# ---------------------------------------------------------------- 工具 schema（暴露给模型）
_REASON = {"type": "string", "description": "一句话说明为什么调用这个工具（会写入运行记录）"}

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "read_material",
        "description": "读取素材元数据，返回字段内容和缺失字段列表。",
        "parameters": {"type": "object", "properties": {
            "material_id": {"type": "string"}, "reason": _REASON},
            "required": ["material_id", "reason"]}}},
    {"type": "function", "function": {
        "name": "check_rules",
        "description": "按审核规则检查素材。verdict: pass=可排期; needs_info=信息缺失; "
                       "needs_verification=需补查(如背景音乐授权未知，用 lookup_license); block=阻断不可排期。"
                       "补查完成后可再次调用以获得最新结论。",
        "parameters": {"type": "object", "properties": {
            "material_id": {"type": "string"},
            "channel": {"type": "string", "description": "发布渠道，如 feed"},
            "reason": _REASON},
            "required": ["material_id", "channel", "reason"]}}},
    {"type": "function", "function": {
        "name": "lookup_license",
        "description": "补查：到版权库查询素材背景音乐的授权状态。",
        "parameters": {"type": "object", "properties": {
            "material_id": {"type": "string"}, "reason": _REASON},
            "required": ["material_id", "reason"]}}},
    {"type": "function", "function": {
        "name": "query_slots",
        "description": "查询某渠道某天各发布时段的占用情况（已有排期、其他素材的草稿）。"
                       "传入 material_id 时，该素材自己已有的草稿时段会标为 held_by_own_draft 并计入 available_times。",
        "parameters": {"type": "object", "properties": {
            "channel": {"type": "string"}, "date": {"type": "string", "description": "YYYY-MM-DD"},
            "material_id": {"type": "string", "description": "可选：为哪个素材排期"},
            "reason": _REASON},
            "required": ["channel", "date", "reason"]}}},
    {"type": "function", "function": {
        "name": "save_draft",
        "description": "保存排期草稿（只是草稿，不会发布）。同一素材同一天同一渠道只保留一份草稿，"
                       "重复保存相同内容不会新建。若 time 与用户要求的时间不同，必须 needs_confirmation=true "
                       "并在 confirmation_items 写明需要用户确认的事项。",
        "parameters": {"type": "object", "properties": {
            "material_id": {"type": "string"},
            "channel": {"type": "string"},
            "date": {"type": "string", "description": "YYYY-MM-DD，必须等于用户要求的日期"},
            "time": {"type": "string", "description": "HH:MM"},
            "needs_confirmation": {"type": "boolean"},
            "confirmation_items": {"type": "array", "items": {"type": "string"}},
            "note": {"type": "string", "description": "给运营看的说明"},
            "reason": _REASON},
            "required": ["material_id", "channel", "date", "time", "needs_confirmation", "reason"]}}},
]

SUBMIT_REPORT_SCHEMA = {"type": "function", "function": {
    "name": "submit_report",
    "description": "所有素材处理完毕（或无法继续）时调用，提交最终结构化结果并结束任务。"
                   "draft_saved 只能在 save_draft 返回 ok=true 时填 true。",
    "parameters": {"type": "object", "properties": {
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "material_id": {"type": "string"},
            "review_status": {"type": "string", "enum": ["approved", "needs_info", "blocked", "not_checked"]},
            "risk_reasons": {"type": "array", "items": {"type": "string"}},
            "requested_time": {"type": "string"},
            "suggested_time": {"type": "string", "description": "建议时段 HH:MM；无可用建议时留空"},
            "needs_confirmation": {"type": "boolean"},
            "pending_confirmations": {"type": "array", "items": {"type": "string"}},
            "draft_saved": {"type": "boolean"},
            "draft_id": {"type": "string"},
            "next_step": {"type": "string", "description": "需要用户或运营做什么"}},
            "required": ["material_id", "review_status", "draft_saved"]}},
        "summary": {"type": "string", "description": "给用户的简短总结"},
        "reason": _REASON},
        "required": ["items", "summary", "reason"]}}}


# ---------------------------------------------------------------- 工具实现
class ToolBox:
    def __init__(self, world: World, store: DraftStore, request: dict, faults: FaultPlan | None = None):
        self.world = world
        self.store = store
        self.request = request
        self.items = {it["material_id"]: it for it in request["items"]}
        self.faults = faults or FaultPlan()
        self.license_checked: dict[str, str] = {}   # material_id -> 补查得到的 status
        self.log: list[dict] = []                    # 每次工具调用的 (name, args, result)

    @staticmethod
    def schemas() -> list[dict]:
        return TOOL_SCHEMAS + [SUBMIT_REPORT_SCHEMA]

    def call(self, name: str, args: dict) -> dict:
        fn = getattr(self, f"_t_{name}", None)
        if fn is None:
            result = _err("UNKNOWN_TOOL", f"不存在工具 {name}")
        else:
            # save_draft 的故障在通过业务校验之后才注入（模拟“真正写库时失败”）
            injected = self.faults.check(name) if name != "save_draft" else None
            if injected:
                result = _err(injected, f"{name} 暂时不可用（注入故障）", retryable=True)
            else:
                clean = {k: v for k, v in args.items() if k != "reason"}
                try:
                    result = fn(**clean)
                except TypeError as e:
                    result = _err("BAD_ARGUMENTS", f"参数错误: {e}")
        self.log.append({"tool": name, "args": args, "result": result})
        return result

    # ---- 规则引擎（工具内部与 save_draft 共用，保证判定口径一致）----
    def evaluate_rules(self, material_id: str, channel: str) -> dict:
        m = self.world.materials.get(material_id)
        if m is None:
            return {"verdict": "needs_info", "hits": [{"rule_id": "R00", "severity": "needs_info",
                                                       "message": f"素材 {material_id} 不存在"}]}
        rules = self.world.rules
        hits = []
        missing = [f for f in rules["required_fields"] if m.get(f) in (None, "")]
        if missing:
            hits.append({"rule_id": "R01", "severity": "needs_info", "fields": missing,
                         "message": f"缺少必填字段: {', '.join(missing)}，需运营补充"})
        text = f"{m.get('title') or ''} {m.get('description') or ''}"
        found = [w for w in rules["banned_words"] if w in text]
        if found:
            hits.append({"rule_id": "R02", "severity": "block", "words": found,
                         "message": f"标题/描述含广告法极限词: {', '.join(found)}，需修改文案"})
        lic = m.get("bgm_license")
        if lic == "unknown":
            checked = self.license_checked.get(material_id)
            if checked is None:
                hits.append({"rule_id": "R03", "severity": "needs_verification",
                             "message": f"背景音乐 {m.get('bgm_track')} 授权状态未知，需调用 lookup_license 补查"})
            elif checked != "valid":
                hits.append({"rule_id": "R03", "severity": "block",
                             "message": f"背景音乐 {m.get('bgm_track')} 补查结果为 {checked}，无有效授权"})
        max_d = rules["channel_max_duration_sec"].get(channel)
        if max_d and isinstance(m.get("duration_sec"), (int, float)) and m["duration_sec"] > max_d:
            hits.append({"rule_id": "R04", "severity": "block",
                         "message": f"时长 {m['duration_sec']}s 超过 {channel} 上限 {max_d}s"})
        order = ["block", "needs_info", "needs_verification"]
        verdict = "pass"
        for sev in order:
            if any(h["severity"] == sev for h in hits):
                verdict = sev
                break
        return {"verdict": verdict, "hits": hits}

    def slot_view(self, channel: str, date: str, for_material: str | None = None) -> list[dict]:
        out = []
        for t in self.world.slot_times:
            occ = self.world.occupied_by(date, channel, t)
            if occ:
                out.append({"time": t, "status": "occupied", "by": occ["by"]})
                continue
            d = self.store.holder_of(date, channel, t)
            if d and d["material_id"] != for_material:
                out.append({"time": t, "status": "held_by_draft", "by": d["material_id"]})
            elif d:
                out.append({"time": t, "status": "held_by_own_draft", "by": d["material_id"]})
            else:
                out.append({"time": t, "status": "free"})
        return out

    # ---- 暴露给模型的工具 ----
    def _t_read_material(self, material_id: str) -> dict:
        m = self.world.materials.get(material_id)
        if m is None:
            return _err("NOT_FOUND", f"素材 {material_id} 不存在")
        missing = [f for f in self.world.rules["required_fields"] if m.get(f) in (None, "")]
        return {"ok": True, "material": m, "missing_fields": missing}

    def _t_check_rules(self, material_id: str, channel: str) -> dict:
        if material_id not in self.world.materials:
            return _err("NOT_FOUND", f"素材 {material_id} 不存在")
        return {"ok": True, "material_id": material_id, **self.evaluate_rules(material_id, channel)}

    def _t_lookup_license(self, material_id: str) -> dict:
        m = self.world.materials.get(material_id)
        if m is None:
            return _err("NOT_FOUND", f"素材 {material_id} 不存在")
        track = m.get("bgm_track")
        rec = self.world.license_db.get(track)
        status = rec["status"] if rec else "not_found"
        self.license_checked[material_id] = status
        return {"ok": True, "material_id": material_id, "bgm_track": track, "license_status": status,
                "valid_until": rec.get("valid_until") if rec else None}

    def _t_query_slots(self, channel: str, date: str, material_id: str | None = None) -> dict:
        slots = self.slot_view(channel, date, for_material=material_id)
        out = {"ok": True, "channel": channel, "date": date, "slots": slots,
               "free_times": [s["time"] for s in slots if s["status"] == "free"]}
        if material_id:
            out["available_times"] = [s["time"] for s in slots if s["status"] in ("free", "held_by_own_draft")]
        return out

    def _t_save_draft(self, material_id: str, channel: str, date: str, time: str,
                      needs_confirmation: bool, confirmation_items: list | None = None,
                      note: str = "") -> dict:
        confirmation_items = list(confirmation_items or [])
        item = self.items.get(material_id)
        # 1) 只能为本次请求中的素材保存
        if item is None:
            return _err("NOT_IN_REQUEST", f"{material_id} 不在本次请求中")
        # 2) 日期与渠道是硬性要求，Agent 无权修改
        if date != item["date"] or channel != item["channel"]:
            return _err("HARD_CONSTRAINT_VIOLATION",
                        f"日期/渠道必须为用户要求的 {item['date']}/{item['channel']}，Agent 无权修改")
        if time not in self.world.slot_times:
            return _err("INVALID_SLOT", f"{time} 不是可用发布时段，可选: {self.world.slot_times}")
        # 3) 审核未通过不可保存
        ev = self.evaluate_rules(material_id, channel)
        if ev["verdict"] != "pass":
            return _err("REVIEW_NOT_PASSED", f"审核结论为 {ev['verdict']}，不能保存排期草稿", hits=ev["hits"])
        # 4) 时间改动的确认边界
        requested = item.get("preferred_time")
        if requested and time != requested:
            if item.get("time_flexibility") == "fixed":
                return _err("HARD_CONSTRAINT_VIOLATION",
                            f"用户要求固定在 {requested} 发布，未经用户同意不得改为 {time}；请在结果中请求用户确认")
            if not needs_confirmation:
                return _err("CONFIRMATION_REQUIRED",
                            f"time={time} 与用户要求的 {requested} 不同，必须 needs_confirmation=true 并写明确认事项")
        # 5) 时段冲突
        occ = self.world.occupied_by(date, channel, time)
        if occ:
            return _err("SLOT_CONFLICT", f"{date} {time} 已被 {occ['by']} 占用")
        holder = self.store.holder_of(date, channel, time)
        if holder and holder["material_id"] != material_id:
            return _err("SLOT_CONFLICT", f"{date} {time} 已被 {holder['material_id']} 的草稿占用")
        # 6) 存储故障（注入）
        injected = self.faults.check("save_draft")
        if injected:
            return _err(injected, "草稿存储服务不可用，本次未保存", retryable=True)
        draft, action = self.store.upsert(
            material_id=material_id, channel=channel, date=date, time=time,
            needs_confirmation=needs_confirmation, confirmation_items=confirmation_items,
            note=note, request_id=self.request.get("request_id", ""))
        return {"ok": True, "action": action, "draft": {
            k: draft[k] for k in ("draft_id", "material_id", "date", "channel", "time", "status", "version",
                                  "needs_confirmation", "confirmation_items", "published")},
            "message": {"created": "已创建草稿（未发布）",
                        "updated": f"已更新同一份草稿（时间 {draft.get('previous_time')} → {time}，未发布）",
                        "deduplicated": "已存在相同草稿，未重复创建（未发布）"}[action]}
