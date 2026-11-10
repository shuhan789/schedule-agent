"""验收用例运行器：读取 examples/cases/*.json，运行 Agent（真实模型或 Mock），保存 Trace，并按 expect 自动核对。

同一套核对逻辑同时用于 Mock 和真实模型，所以真实模型跑出来的结果也能得到“预期 vs 实际”的结论。
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .agent import Limits, run_agent
from .llm import ScriptedLLM
from .store import PROJECT_ROOT, DraftStore, World
from .tools import FaultPlan, ToolBox
from .trace import Trace

CASES_DIR = PROJECT_ROOT / "examples" / "cases"


def load_cases(only: list[str] | None = None) -> list[dict]:
    cases = []
    for p in sorted(CASES_DIR.glob("*.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        c.setdefault("name", p.stem)
        if only and not any(o in c["name"] for o in only):
            continue
        cases.append(c)
    return cases


def _runs(case: dict) -> list[dict]:
    if "runs" in case:
        return case["runs"]
    return [{k: case[k] for k in ("faults", "schedule_overrides", "mock_script") if k in case}]


def run_case(case: dict, llm_factory, mode: str, out_root: Path, state_root: Path) -> dict:
    state_dir = state_root / mode / case["name"]
    if state_dir.exists():
        shutil.rmtree(state_dir)  # 每个用例从干净状态开始；同一用例的多次运行共享状态（用于重复提交）
    store = DraftStore(state_dir)
    limits = Limits(**case.get("limits", {}))
    runs = _runs(case)
    finals, logs, worlds = [], [], []
    for i, run in enumerate(runs, start=1):
        world = World(schedule_overrides=run.get("schedule_overrides"))
        toolbox = ToolBox(world, store, case["request"], FaultPlan(spec=dict(run.get("faults", {}))))
        llm = llm_factory(run)
        trace = Trace({"case": case["name"], "mode": mode, "model": llm.describe(),
                       "request_id": case["request"].get("request_id"), "run_index": i,
                       "max_steps": limits.max_steps, "max_tool_calls": limits.max_tool_calls})
        final = run_agent(case["request"], llm, toolbox, limits, trace)
        out_dir = out_root / "runs" / mode / case["name"] / (f"run{i}" if len(runs) > 1 else "")
        trace.save(out_dir, final)
        finals.append(final)
        logs.append(toolbox.log)
        worlds.append(world)
    checks = check_expectations(case, finals, logs, store, worlds[-1])
    last = finals[-1]
    return {
        "case": case["name"], "title": case.get("title", ""), "covers": case.get("covers", []),
        "mode": mode, "runs": len(runs),
        "task_status": last["task_status"],
        "final_states": {it["material_id"]: it["final_state"] for it in last["items"]},
        "guard_notes": sum(len(f["guard_notes"]) for f in finals),
        "tool_calls": sum(len(lg) for lg in logs),
        "checks": checks, "passed": all(c["passed"] for c in checks),
        "trace_dir": _rel(out_root / "runs" / mode / case["name"]),
    }


def _rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(p)


def _chk(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "passed": bool(ok), "detail": detail}


def check_expectations(case: dict, finals: list[dict], logs: list[list], store: DraftStore, world: World) -> list:
    exp = case.get("expect", {})
    last = finals[-1]
    items = {it["material_id"]: it for it in last["items"]}
    drafts = store.all()
    res = []

    # ---- 全局不变量（每个用例都检查）----
    res.append(_chk("从未发布", all(f["published"] is False for f in finals) and
                    all(d.get("published") is False for d in drafts), "published 字段恒为 False"))
    slots = {}
    clash = []
    for d in drafts:
        k = (d["date"], d["channel"], d["time"])
        if k in slots:
            clash.append(f"{k} 被 {slots[k]} 和 {d['material_id']} 同时占用")
        slots[k] = d["material_id"]
        occ = world.occupied_by(*k)
        if occ:
            clash.append(f"{d['material_id']} 草稿落在已占用时段 {k}（{occ['by']}）")
    res.append(_chk("草稿无时段冲突", not clash, "; ".join(clash) or "无冲突"))
    truthful = []
    for it in last["items"]:
        d = it["draft"]
        if d["saved"]:
            hit = [x for x in drafts if x["draft_id"] == d["draft_id"] and x["time"] == d["time"]]
            if not hit:
                truthful.append(f"{it['material_id']} 报告已保存但存储中不存在")
    res.append(_chk("保存状态与存储一致", not truthful, "; ".join(truthful) or "一致"))

    # ---- 用例专属预期 ----
    if "task_status_in" in exp:
        res.append(_chk(f"task_status ∈ {exp['task_status_in']}", last["task_status"] in exp["task_status_in"],
                        f"实际 {last['task_status']}（{last.get('status_reason', '')}）"))
    if "status_reason_contains" in exp:
        res.append(_chk(f"状态原因包含“{exp['status_reason_contains']}”",
                        exp["status_reason_contains"] in last.get("status_reason", ""), last.get("status_reason", "")))
    for mid, e in exp.get("items", {}).items():
        it = items.get(mid)
        if it is None:
            res.append(_chk(f"{mid} 出现在结果中", False))
            continue
        if "final_state_in" in e:
            res.append(_chk(f"{mid} 最终状态 ∈ {e['final_state_in']}", it["final_state"] in e["final_state_in"],
                            f"实际 {it['final_state']}"))
        if "review_status" in e:
            res.append(_chk(f"{mid} 审核结论 = {e['review_status']}", it["review_status"] == e["review_status"],
                            f"实际 {it['review_status']}；风险: {it['risk_reasons']}"))
        if "time_in" in e:
            res.append(_chk(f"{mid} 建议时段 ∈ {e['time_in']}", it["suggested_time"] in e["time_in"],
                            f"实际 {it['suggested_time']}"))
        if "time_not_in" in e:
            res.append(_chk(f"{mid} 建议时段 ∉ {e['time_not_in']}", it["suggested_time"] not in e["time_not_in"],
                            f"实际 {it['suggested_time']}"))
        if "needs_confirmation" in e:
            res.append(_chk(f"{mid} 待确认 = {e['needs_confirmation']}",
                            it["needs_confirmation"] == e["needs_confirmation"],
                            f"实际 {it['needs_confirmation']}；{it['pending_confirmations']}"))
        if "draft_saved" in e:
            res.append(_chk(f"{mid} 草稿已保存 = {e['draft_saved']}", it["draft"]["saved"] == e["draft_saved"],
                            json.dumps(it["draft"], ensure_ascii=False)))
        if "draft_action_in" in e:
            res.append(_chk(f"{mid} 草稿动作 ∈ {e['draft_action_in']}", it["draft"]["action"] in e["draft_action_in"],
                            f"实际 {it['draft']['action']}"))
        if "risk_mentions" in e:
            text = " ".join(it["risk_reasons"])
            miss = [w for w in e["risk_mentions"] if w not in text]
            res.append(_chk(f"{mid} 风险原因提及 {e['risk_mentions']}", not miss, text))
    for mid, e in exp.get("store", {}).items():
        mine = [d for d in drafts if d["material_id"] == mid]
        if "count" in e:
            res.append(_chk(f"存储中 {mid} 草稿数 = {e['count']}", len(mine) == e["count"],
                            f"实际 {len(mine)}：{[(d['draft_id'], d['time'], 'v' + str(d['version'])) for d in mine]}"))
        if "time_not_in" in e:
            bad = [d["time"] for d in mine if d["time"] in e["time_not_in"]]
            res.append(_chk(f"存储中 {mid} 时段 ∉ {e['time_not_in']}", not bad, f"实际 {[d['time'] for d in mine]}"))
    for tc in exp.get("tool_called", []):
        run_idx = tc.get("run", len(logs)) - 1
        hit = [e for e in logs[run_idx] if e["tool"] == tc["tool"]
               and all(e["args"].get(k) == v for k, v in tc.get("args", {}).items())]
        need = tc.get("min", 1)
        res.append(_chk(f"第{run_idx + 1}次运行调用 {tc['tool']} {tc.get('args', {})} ≥ {need} 次", len(hit) >= need,
                        f"实际 {len(hit)} 次"))
    return res


def mock_factory(run: dict):
    return ScriptedLLM(run.get("mock_script", []))


def write_summary(results: list[dict], mode: str, out_root: Path, model_desc: str) -> Path:
    res_dir = out_root / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    (res_dir / f"{mode}_summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    n_pass = sum(r["passed"] for r in results)
    lines = [f"# 用例运行汇总（{mode}）", "", f"- 模型：{model_desc}",
             f"- 通过：**{n_pass}/{len(results)}**", ""]
    if mode == "mock":
        lines += ["> Mock 回放预设动作，只证明工具、循环、对账、Trace 管道正确，不代表真实模型决策效果。", ""]
    lines += ["| 用例 | 覆盖验收点 | 任务状态 | 各素材最终状态 | 工具调用 | Guard更正 | 结果 | Trace |",
              "|---|---|---|---|---|---|---|---|"]
    for r in results:
        st = ", ".join(f"{k}:{v}" for k, v in r["final_states"].items())
        lines.append(f"| {r['case']} | {'、'.join(r['covers'])} | {r['task_status']} | {st} | {r['tool_calls']} | "
                     f"{r['guard_notes']} | {'✅' if r['passed'] else '❌'} | `{r['trace_dir']}/` |")
    lines += ["", "## 逐项核对", ""]
    for r in results:
        lines += [f"### {r['case']} — {r['title']}", ""]
        for c in r["checks"]:
            lines.append(f"- {'✅' if c['passed'] else '❌'} {c['name']} — {c['detail']}")
        lines.append("")
    p = res_dir / f"{mode}_summary.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p
