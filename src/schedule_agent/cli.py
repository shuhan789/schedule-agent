"""命令行入口。

python main.py run-all [--mock] [--only case02]       运行全部/部分验收用例并自动核对
python main.py run --request my_request.json [--fail save_draft]   用真实模型处理自定义请求
python main.py drafts                                 查看草稿
python main.py confirm DRAFT-XXXX                     用户确认草稿（仍是草稿，不发布）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent import Limits, run_agent
from .cases import load_cases, mock_factory, run_case, write_summary
from .llm import LLMError, OpenAICompatLLM
from .store import PROJECT_ROOT, DraftStore, World
from .tools import FaultPlan, ToolBox
from .trace import Trace


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass


def _real_llm() -> OpenAICompatLLM:
    try:
        return OpenAICompatLLM()
    except LLMError as e:
        print(f"[错误] {e}", file=sys.stderr)
        sys.exit(2)


def cmd_run_all(a) -> int:
    cases = load_cases(a.only)
    if not cases:
        print("没有匹配的用例")
        return 1
    out_root = Path(a.out).resolve()
    state_root = Path(a.state_dir).resolve()
    if a.mock:
        factory, mode, desc = mock_factory, "mock", "ScriptedLLM (离线 Mock)"
    else:
        llm = _real_llm()
        factory, mode, desc = (lambda run: llm), "real", llm.describe()
    results = []
    for c in cases:
        print(f"▶ {c['name']} ...", flush=True)
        r = run_case(c, factory, mode, out_root, state_root)
        results.append(r)
        print(f"  {'✅' if r['passed'] else '❌'} task_status={r['task_status']} {r['final_states']}"
              f" guard更正={r['guard_notes']}")
        for ch in r["checks"]:
            if not ch["passed"]:
                print(f"     ✗ {ch['name']} — {ch['detail']}")
    p = write_summary(results, mode, out_root, desc)
    print(f"\n通过 {sum(r['passed'] for r in results)}/{len(results)}，汇总：{p}")
    return 0 if all(r["passed"] for r in results) else 1


def cmd_run(a) -> int:
    request = json.loads(Path(a.request).read_text(encoding="utf-8"))
    store = DraftStore(a.state_dir)
    faults = FaultPlan(spec={t: {"mode": "always"} for t in (a.fail or [])})
    toolbox = ToolBox(World(), store, request, faults)
    llm = _real_llm()
    limits = Limits(max_steps=a.max_steps, max_tool_calls=a.max_tool_calls)
    trace = Trace({"case": Path(a.request).stem, "mode": "real", "model": llm.describe(),
                   "request_id": request.get("request_id"), "max_steps": limits.max_steps,
                   "max_tool_calls": limits.max_tool_calls})
    final = run_agent(request, llm, toolbox, limits, trace)
    out = Path(a.out) / Path(a.request).stem
    trace.save(out, final)
    print(trace.to_markdown(final))
    print(f"Trace 已保存到 {out}/")
    return 0


def cmd_drafts(a) -> int:
    for d in DraftStore(a.state_dir).all():
        print(f"{d['draft_id']}  {d['material_id']}  {d['date']} {d['time']} {d['channel']}  "
              f"status={d['status']} v{d['version']} published={d['published']}")
    return 0


def cmd_confirm(a) -> int:
    d = DraftStore(a.state_dir).confirm(a.draft_id)
    if not d:
        print(f"未找到草稿 {a.draft_id}")
        return 1
    print(f"已由用户确认 {d['draft_id']}（{d['material_id']} {d['date']} {d['time']}）。仍为草稿，未发布。")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows 中文控制台(GBK)下避免符号输出报错
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    _load_env()
    p = argparse.ArgumentParser(prog="schedule-agent", description="素材审核与发布排期 Agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run-all", help="运行验收用例并自动核对")
    r.add_argument("--mock", action="store_true", help="离线 Mock（回放预设动作，仅验证流程）")
    r.add_argument("--only", nargs="*", help="只运行名称包含这些关键字的用例")
    r.add_argument("--out", default=str(PROJECT_ROOT / "examples"))
    r.add_argument("--state-dir", default=str(PROJECT_ROOT / ".state"))
    r.set_defaults(fn=cmd_run_all)

    r = sub.add_parser("run", help="用真实模型处理一个自定义请求 JSON")
    r.add_argument("--request", required=True)
    r.add_argument("--fail", nargs="*", help="注入故障的工具名，如 save_draft query_slots")
    r.add_argument("--max-steps", type=int, default=15)
    r.add_argument("--max-tool-calls", type=int, default=40)
    r.add_argument("--state-dir", default=str(PROJECT_ROOT / ".state" / "manual"))
    r.add_argument("--out", default=str(PROJECT_ROOT / "examples" / "runs" / "manual"))
    r.set_defaults(fn=cmd_run)

    for name, fn, h in (("drafts", cmd_drafts, "查看草稿"), ("confirm", cmd_confirm, "用户确认草稿")):
        r = sub.add_parser(name, help=h)
        if name == "confirm":
            r.add_argument("draft_id")
        r.add_argument("--state-dir", default=str(PROJECT_ROOT / ".state" / "manual"))
        r.set_defaults(fn=fn)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
