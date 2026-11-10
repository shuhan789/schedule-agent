"""ReAct 循环：模型选择动作 → 执行工具 → 把结果作为观察回传 → 模型决定下一步或提交结果。

循环本身不含业务分支：下一步调用哪个工具、传什么参数、是否重试、何时结束，都由模型根据工具结果决定。
循环只负责：执行工具、记录 Trace、执行步数/调用次数上限、在结束时调用 guard 对账。
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .guard import reconcile
from .llm import LLMError
from .prompts import SYSTEM_PROMPT, render_request
from .tools import ToolBox
from .trace import Trace, summarize


@dataclass
class Limits:
    max_steps: int = 15        # 最多调用模型的轮数
    max_tool_calls: int = 40   # 最多执行的工具调用次数（含 submit_report）


def run_agent(request: dict, llm, toolbox: ToolBox, limits: Limits, trace: Trace) -> dict:
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": render_request(request)}]
    tools = toolbox.schemas()
    tool_calls_used = 0
    nudged = False
    report = None
    termination = {"submitted": False, "reason": ""}

    def finish() -> dict:
        return reconcile(request, report, toolbox.log, toolbox.store, termination)

    for turn in range(1, limits.max_steps + 1):
        try:
            resp = llm.chat(messages, tools)
        except LLMError as e:
            trace.add(turn=turn, action="llm_error", args={}, summary=str(e)[:200], reason="")
            termination["reason"] = f"未完成：模型调用失败（{str(e)[:120]}）"
            return finish()

        if not resp.tool_calls:
            trace.add(turn=turn, action="model_text", args={}, summary=(resp.content or "")[:200], reason="")
            messages.append(resp.to_message())
            if nudged:
                termination["reason"] = "未完成：模型未通过 submit_report 提交结果"
                return finish()
            nudged = True
            messages.append({"role": "user", "content": "请继续处理；全部素材有结论后，必须调用 submit_report 提交结构化结果。"})
            continue

        messages.append(resp.to_message())
        for tc in resp.tool_calls:
            if tool_calls_used >= limits.max_tool_calls:
                trace.add(turn=turn, action="limit_reached", args={}, reason="",
                          summary=f"工具调用次数达到上限 {limits.max_tool_calls}")
                termination["reason"] = f"未完成：工具调用次数达到上限 {limits.max_tool_calls}"
                return finish()
            tool_calls_used += 1
            try:
                args = json.loads(tc.arguments or "{}")
                if not isinstance(args, dict):
                    raise ValueError("参数必须是 JSON 对象")
            except (json.JSONDecodeError, ValueError) as e:
                result = {"ok": False, "error_code": "BAD_ARGUMENTS_JSON", "message": f"参数不是合法 JSON: {e}"}
                trace.add(turn=turn, action=tc.name, args={"raw": tc.arguments[:200]}, reason="",
                          ok=False, summary=result["message"])
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(result, ensure_ascii=False)})
                continue

            reason = args.get("reason", "")
            shown_args = {k: v for k, v in args.items() if k != "reason"}

            if tc.name == "submit_report":
                if not isinstance(args.get("items"), list):
                    result = {"ok": False, "error_code": "BAD_REPORT", "message": "items 必须是数组"}
                    trace.add(turn=turn, action=tc.name, args={}, reason=reason, ok=False, summary=result["message"])
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": json.dumps(result, ensure_ascii=False)})
                    continue
                report = args
                termination = {"submitted": True, "reason": "模型已提交结果"}
                trace.add(turn=turn, action="submit_report", args={"items": len(args["items"])},
                          reason=reason, ok=True, summary="提交最终结果")
                return finish()

            result = toolbox.call(tc.name, args)
            trace.add(turn=turn, action=tc.name, args=shown_args, reason=reason,
                      ok=bool(result.get("ok")), summary=summarize(tc.name, result))
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False)})

    trace.add(turn=limits.max_steps, action="limit_reached", args={}, reason="",
              summary=f"模型调用轮数达到上限 {limits.max_steps}")
    termination["reason"] = f"未完成：模型调用轮数达到上限 {limits.max_steps}"
    return finish()
