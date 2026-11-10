"""运行记录（Trace）：步骤、工具参数、返回摘要、后续动作、决策依据。
不记录模型内部思维过程；“决策依据”来自模型在每次工具调用时填写的 reason 参数。"""
from __future__ import annotations

import json
from pathlib import Path


def summarize(tool: str, result: dict) -> str:
    if not isinstance(result, dict):
        return str(result)[:120]
    if not result.get("ok", True):
        return f"失败 {result.get('error_code')}: {result.get('message', '')}" + (
            "（可重试）" if result.get("retryable") else "")
    if tool == "read_material":
        m = result["material"]
        miss = result.get("missing_fields") or []
        return f"《{m.get('title')}》 bgm={m.get('bgm_license')}" + (f"，缺失字段: {miss}" if miss else "，字段完整")
    if tool == "check_rules":
        hits = "; ".join(f"{h['rule_id']}({h['severity']})" for h in result.get("hits", []))
        return f"verdict={result['verdict']}" + (f"，命中: {hits}" if hits else "")
    if tool == "lookup_license":
        return f"{result['bgm_track']} 授权状态={result['license_status']}"
    if tool == "query_slots":
        busy = [f"{s['time']}({s['status']}:{s.get('by')})" for s in result["slots"] if s["status"] != "free"]
        return f"空闲: {result['free_times']}；占用: {busy}"
    if tool == "save_draft":
        d = result["draft"]
        return f"{result['action']} {d['draft_id']} {d['time']} status={d['status']} v{d['version']}"
    return json.dumps(result, ensure_ascii=False)[:160]


class Trace:
    def __init__(self, meta: dict):
        self.meta = meta
        self.steps: list[dict] = []

    def add(self, **kw) -> None:
        self.steps.append(kw)

    def to_dict(self, final: dict | None = None) -> dict:
        return {"meta": self.meta, "steps": self.steps, "final": final}

    def save(self, out_dir: Path, final: dict) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "trace.json", "w", encoding="utf-8") as f:
            json.dump(self.to_dict(final), f, ensure_ascii=False, indent=2)
        with open(out_dir / "output.json", "w", encoding="utf-8") as f:
            json.dump(final, f, ensure_ascii=False, indent=2)
        (out_dir / "trace.md").write_text(self.to_markdown(final), encoding="utf-8")

    def to_markdown(self, final: dict) -> str:
        m = self.meta
        lines = [f"# 运行记录：{m.get('case', '')}", "",
                 f"- 模式：**{m.get('mode')}**（{m.get('model')}）",
                 f"- 请求：`{m.get('request_id')}`  运行序号：{m.get('run_index', 1)}",
                 f"- 上限：最多 {m.get('max_steps')} 轮模型调用 / {m.get('max_tool_calls')} 次工具调用", ""]
        if m.get("mode") == "mock":
            lines += ["> 离线 Mock：动作序列是预先写好的回放，只验证流程，不代表真实模型决策。", ""]
        lines += ["| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |", "|---|---|---|---|---|---|---|"]
        for i, s in enumerate(self.steps):
            nxt = self.steps[i + 1]["action"] if i + 1 < len(self.steps) else "（结束）"
            args = json.dumps(s.get("args", {}), ensure_ascii=False).replace("|", "\\|")
            lines.append(f"| {i + 1} | {s.get('turn')} | `{s['action']}` | {args} | "
                         f"{str(s.get('summary', '')).replace('|', '/')} | {s.get('reason', '')} | `{nxt}` |")
        lines += ["", "## 最终结果", "",
                  f"- task_status: **{final['task_status']}**  {final.get('status_reason', '')}",
                  f"- published: {final['published']}", ""]
        lines += ["| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |",
                  "|---|---|---|---|---|---|---|---|"]
        for it in final["items"]:
            d = it["draft"]
            dtxt = (f"{d['action']} {d.get('draft_id')} ({d.get('status')})" if d["saved"]
                    else f"未保存: {d['action']} {d.get('error_code') or ''}")
            lines.append(f"| {it['material_id']} | {it['review_status']} | {'；'.join(it['risk_reasons']) or '-'} | "
                         f"{it['requested_time']} | {it['suggested_time'] or '-'} | "
                         f"{'；'.join(it['pending_confirmations']) or '-'} | {dtxt} | {it['final_state']} |")
        lines += ["", f"**总结**：{final.get('summary') or '-'}", ""]
        if final.get("guard_notes"):
            lines += ["**Guard 更正记录**（模型报告与工具记录不一致之处）：", ""]
            lines += [f"- {n}" for n in final["guard_notes"]]
        return "\n".join(lines) + "\n"
