"""Agent 循环与 Guard 对账。用 ScriptedLLM 模拟“出错的模型”，验证系统不会把错误结论交给用户。"""
import json
from types import SimpleNamespace

from conftest import CH, DATE, item

from schedule_agent.agent import Limits, run_agent
from schedule_agent.llm import OpenAICompatLLM, ScriptedLLM
from schedule_agent.trace import Trace


def T(tool, **args):
    args.setdefault("reason", "测试")
    return {"tool": tool, "args": args}


def run(tb, script, **limits):
    trace = Trace({"case": "t", "mode": "mock"})
    final = run_agent(tb.request, ScriptedLLM(script), tb, Limits(**limits), trace)
    return final, trace


def test_false_save_claim_is_corrected(make_toolbox, store):
    tb = make_toolbox([item("M02", "20:00")], faults={"save_draft": {"mode": "always"}})
    script = [[T("save_draft", material_id="M02", channel=CH, date=DATE, time="20:00", needs_confirmation=False)],
              [T("submit_report", items=[{"material_id": "M02", "review_status": "approved", "draft_saved": True,
                                          "draft_id": "DRAFT-FAKE"}],
                 summary="M02 已发布成功！")]]
    final, _ = run(tb, script)
    it = final["items"][0]
    assert it["draft"]["saved"] is False and it["final_state"] in ("save_failed", "unresolved")
    assert "已发布" not in final["summary"]
    assert any("声称草稿已保存" in n for n in final["guard_notes"])
    assert any("越权" in n for n in final["guard_notes"])
    assert final["published"] is False


def test_review_claim_uses_tool_record(make_toolbox):
    tb = make_toolbox([item("M06", "20:00")])
    script = [[T("check_rules", material_id="M06", channel=CH)],
              [T("submit_report", items=[{"material_id": "M06", "review_status": "approved", "draft_saved": False}],
                 summary="ok")]]
    final, _ = run(tb, script)
    assert final["items"][0]["review_status"] == "blocked"
    assert any("审核结论" in n for n in final["guard_notes"])


def test_missing_item_in_report_is_filled(make_toolbox):
    tb = make_toolbox([item("M01", "18:00"), item("M02", "20:00")])
    script = [[T("submit_report", items=[{"material_id": "M01", "review_status": "not_checked", "draft_saved": False}],
                 summary="")]]
    final, _ = run(tb, script)
    assert {i["material_id"] for i in final["items"]} == {"M01", "M02"}
    assert final["task_status"] == "partial_failed"


def test_step_limit_returns_incomplete(make_toolbox):
    tb = make_toolbox([item("M02", "20:00")])
    script = [[T("read_material", material_id="M02")]] * 10
    final, trace = run(tb, script, max_steps=3)
    assert final["task_status"] == "incomplete" and "上限" in final["status_reason"]
    assert trace.steps[-1]["action"] == "limit_reached"


def test_tool_call_limit_returns_incomplete(make_toolbox):
    tb = make_toolbox([item("M02", "20:00")])
    script = [[T("read_material", material_id="M02")] * 5]
    final, _ = run(tb, script, max_tool_calls=3)
    assert final["task_status"] == "incomplete" and "工具调用次数" in final["status_reason"]
    assert len(tb.log) == 3


def test_partial_progress_survives_limit(make_toolbox):
    """达到上限时，已保存的草稿如实体现在结果里。"""
    tb = make_toolbox([item("M02", "20:00")])
    script = [[T("save_draft", material_id="M02", channel=CH, date=DATE, time="20:00", needs_confirmation=False)],
              [T("read_material", material_id="M02")], [T("read_material", material_id="M02")]]
    final, _ = run(tb, script, max_steps=2)
    assert final["task_status"] == "incomplete"
    assert final["items"][0]["draft"]["saved"] is True


def test_text_reply_is_nudged_then_incomplete(make_toolbox):
    tb = make_toolbox([item("M02", "20:00")])
    final, trace = run(tb, [{"text": "我觉得可以发布"}, {"text": "好的"}])
    assert final["task_status"] == "incomplete" and "submit_report" in final["status_reason"]
    assert [s["action"] for s in trace.steps] == ["model_text", "model_text"]


def test_bad_json_arguments_become_observation(make_toolbox):
    tb = make_toolbox([item("M02", "20:00")])
    script = [[{"tool": "read_material", "args": "{not json"}],
              [T("submit_report", items=[], summary="")]]
    final, trace = run(tb, script)
    assert trace.steps[0]["ok"] is False and "JSON" in trace.steps[0]["summary"]


def test_llm_error_returns_incomplete(make_toolbox):
    tb = make_toolbox([item("M02", "20:00")])
    final, _ = run(tb, [{"raise": "401 invalid api key"}])
    assert final["task_status"] == "incomplete" and "模型调用失败" in final["status_reason"]


# ---------------- 真实模型接入的消息格式（用假客户端，不联网） ----------------
class FakeCompletions:
    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def create(self, **kw):
        self.seen.append(json.loads(json.dumps(kw["messages"], ensure_ascii=False)))
        name, args = self.replies.pop(0)
        tc = SimpleNamespace(id=f"call_{len(self.seen)}", function=SimpleNamespace(name=name, arguments=json.dumps(args)))
        msg = SimpleNamespace(content=None, tool_calls=[tc])
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_openai_compat_message_flow(make_toolbox, monkeypatch):
    tb = make_toolbox([item("M02", "20:00")])
    llm = OpenAICompatLLM(api_key="test-key", base_url="http://localhost:9", model="fake")
    fake = FakeCompletions([
        ("read_material", {"material_id": "M02", "reason": "r"}),
        ("submit_report", {"items": [{"material_id": "M02", "review_status": "not_checked", "draft_saved": False}],
                           "summary": "", "reason": "r"}),
    ])
    llm.client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    run_agent(tb.request, llm, tb, Limits(), Trace({"mode": "real"}))
    second_call = fake.seen[1]
    assistant, tool_msg = second_call[-2], second_call[-1]
    assert assistant["role"] == "assistant" and assistant["tool_calls"][0]["id"] == "call_1"
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "call_1"
    assert json.loads(tool_msg["content"])["ok"] is True
