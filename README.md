# 素材审核与发布排期 Agent（项目题 1）

帮助内容团队审核待发布素材，并形成**无冲突、可确认**的发布排期草稿。
Agent 由大模型通过 function calling 驱动：模型选择工具 → 执行 → 观察结果 → 决定下一步或提交结果。
系统**只保存草稿，没有任何发布能力**。

## 评审入口

| 想看什么 | 去哪里 |
|---|---|
| 验收点 ↔ 用例 ↔ 结果对照 | [docs/03-evaluation.md](docs/03-evaluation.md) |
| 真实模型运行汇总（自动核对） | [examples/results/real_summary.md](examples/results/real_summary.md)（`python main.py run-all` 生成） |
| 真实模型逐步 Trace | `examples/runs/real/<用例>/trace.md` |
| 离线 Mock 运行汇总 | [examples/results/mock_summary.md](examples/results/mock_summary.md) |
| 调用流程与设计取舍 | [docs/02-solution.md](docs/02-solution.md) |
| ReAct 循环 | [src/schedule_agent/agent.py](src/schedule_agent/agent.py) |
| 硬约束（防越权、防冲突、防重复） | [src/schedule_agent/tools.py](src/schedule_agent/tools.py) 中 `_t_save_draft` |
| 结果对账（防虚报保存成功） | [src/schedule_agent/guard.py](src/schedule_agent/guard.py) |

## 环境

- Python 3.10+（开发时用 3.13）
- 一个 OpenAI 兼容、支持 function calling 的模型接口（默认 DeepSeek `deepseek-chat`）；离线 Mock 不需要

## 安装

```bash
git clone <本仓库URL> && cd <仓库目录>
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 运行

### 1. 离线 Mock（无需 Key，验证流程）

```bash
python main.py run-all --mock
```

回放 `examples/cases/*.json` 里预写的动作序列，跑完全部 12 个用例并自动核对。
**边界：Mock 不看工具结果，只证明工具、循环、对账、Trace 管道正确，不证明模型决策能力。**

### 2. 真实模型（证明决策能力）

```bash
cp .env.example .env          # Windows: copy .env.example .env
# 编辑 .env，填写 LLM_API_KEY
python main.py run-all        # 跑全部用例，输出到 examples/runs/real/ 与 examples/results/real_summary.md
python main.py run-all --only case02 case07   # 只跑部分用例
```

### 3. 自定义请求 / 故障注入

```bash
python main.py run --request examples/requests/sample_request.json
python main.py run --request examples/requests/sample_request.json --fail save_draft   # 注入保存失败
python main.py drafts                         # 查看草稿
python main.py confirm DRAFT-XXXXXXXX         # 由用户确认草稿（确认后仍是草稿，不发布）
```

### 4. 测试

```bash
python -m pytest -q
```

42 个测试：工具硬约束、Guard 对账、循环上限与异常、OpenAI 消息格式、12 个验收用例（Mock）。

## 目录

```
main.py                    入口（自动把 src/ 加入路径，无需安装）
src/schedule_agent/
  agent.py                 ReAct 循环、步数/调用上限
  tools.py                 5 个业务工具 + submit_report；save_draft 内置硬约束；故障注入
  store.py                 合成数据加载；草稿存储（幂等、单素材单草稿）
  guard.py                 结果对账：以工具记录为准更正模型报告
  llm.py                   OpenAI 兼容接入；离线 ScriptedLLM
  prompts.py               系统提示词
  trace.py                 Trace 记录与 Markdown 渲染
  cases.py                 用例运行与自动核对
  cli.py                   命令行
data/                      合成素材、审核规则、已有排期、版权库
examples/cases/            12 个验收用例（输入、故障注入、预期、Mock 脚本）
examples/runs/{mock,real}/ 每个用例的 trace.md / trace.json / output.json
examples/results/          运行汇总（预期 vs 实际）
tests/                     pytest
docs/                      01~05 文档
```

## 已知限制

见 [docs/03-evaluation.md](docs/03-evaluation.md#已知限制)。
