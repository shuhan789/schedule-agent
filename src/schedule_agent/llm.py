"""模型接入。

- OpenAICompatLLM：任意 OpenAI 兼容接口（DeepSeek / 通义 / Kimi / OpenAI ...），使用原生 function calling。
- ScriptedLLM：离线 Mock，按预先写好的动作序列逐轮“回放”，不看工具结果。
  它只用来验证 Agent 循环、工具、校验、Trace 这条管道能跑通，不能证明模型的决策能力。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON 字符串，与 OpenAI 格式一致


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)

    def to_message(self) -> dict:
        msg: dict = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": tc.arguments}}
                for tc in self.tool_calls
            ]
        return msg


class LLMError(RuntimeError):
    pass


class OpenAICompatLLM:
    mode = "real"

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None,
                 temperature: float = 0.0, timeout: float = 60.0):
        from openai import OpenAI  # 延迟导入，离线 Mock 不依赖网络

        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "deepseek-chat")
        if not self.api_key:
            raise LLMError("未设置 LLM_API_KEY。请复制 .env.example 为 .env 并填写，或使用 --mock 离线运行。")
        self.temperature = temperature
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=timeout, max_retries=2)

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        try:
            r = self.client.chat.completions.create(
                model=self.model, messages=messages, tools=tools, tool_choice="auto",
                temperature=self.temperature,
            )
        except Exception as e:  # 网络、鉴权、限流等
            raise LLMError(f"{type(e).__name__}: {e}") from e
        msg = r.choices[0].message
        calls = [ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments or "{}")
                 for tc in (msg.tool_calls or [])]
        return LLMResponse(content=msg.content or "", tool_calls=calls)

    def describe(self) -> str:
        return f"{self.model} @ {self.base_url}"


class ScriptedLLM:
    """离线 Mock。script 是“轮”的列表；每轮是一个动作列表 [{"tool": 名称, "args": {...}}]，
    或 {"text": "..."} 表示这一轮模型只回复文字。脚本用完后返回空文字（循环会按未提交处理）。"""
    mode = "mock"

    def __init__(self, script: list):
        self.script = list(script)
        self.turn = 0

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        if self.turn >= len(self.script):
            return LLMResponse(content="（Mock 脚本已结束）")
        turn = self.script[self.turn]
        self.turn += 1
        if isinstance(turn, dict) and "text" in turn:
            return LLMResponse(content=turn["text"])
        if isinstance(turn, dict) and "raise" in turn:
            raise LLMError(turn["raise"])
        calls = []
        for i, act in enumerate(turn):
            args = act.get("args", {})
            raw = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
            calls.append(ToolCall(id=f"mock_{self.turn}_{i}", name=act["tool"], arguments=raw))
        return LLMResponse(tool_calls=calls)

    def describe(self) -> str:
        return "ScriptedLLM (离线 Mock，回放预设动作)"
