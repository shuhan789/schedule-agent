# 04 AI 使用说明

## 使用的 AI 工具

| 工具 | 用途 |
|---|---|
| Claude（claude.ai，模型 Claude Opus 5.5） | 根据我的想法生成代码；指导环境配置与 GitHub 推送；讲解代码 |

除 Claude 外没有使用其他 AI 工具。DeepSeek `deepseek-chat` 是项目运行时调用的模型，不是辅助开发的工具。

## 分工

| 环节 | 我 | Claude |
|---|---|---|
| 选题 | 选择第 1 题 | — |
| 方案设计 | 设计“模型决策 / 工具层硬约束 / Guard 对账”三层分工，以及草稿主键加指纹的防重复方案 | — |
| 代码 | 提出实现思路，阅读全部源代码与测试 | 根据我的思路生成 `src/`、`tests/`、`data/` 下的代码与合成数据 |
| 测试用例 | 设计 12 个验收场景，覆盖题目全部验收点 | 把场景写成用例文件与 Mock 脚本 |
| 模型选型 | 选择 DeepSeek，注册账号、充值并配置 Key | — |
| 真实运行 | 在本机（MacBook M2）用真实模型运行全部用例，产出 `examples/runs/real/` 与 `real_summary.md` | — |
| 环境与发布 | 在本机完成安装、运行与推送 | 指导环境配置与 GitHub 推送 |

## 我做了什么

- **选题与设计**：选择第 1 题；设计三层分工和防重复方案；设计 12 个验收场景。
- **阅读代码**：读了全部源代码文件（`agent.py`、`tools.py`、`store.py`、`guard.py`、`prompts.py`、`llm.py`、`trace.py`、`cases.py`、`cli.py`）和测试，并结合运行记录核对实现：同一份草稿 DRAFT-CF6562FB 在 case02 中 created，在 case06 中 deduplicated，在 case07 中 updated 为 v2。
- **本机运行与验证**：安装依赖，运行测试、离线 Mock 和真实模型，逐条阅读真实 Trace。
- **排查问题**：`git push` 报 `Failed to connect to github.com port 443`。原因是浏览器走系统代理，git 没有走代理。用 `scutil --proxy` 查到本机代理端口，给 git 配置 `http.proxy` 后推送成功。

## 验证方式

| 验证 | 方式 | 结果 |
|---|---|---|
| 验收用例（真实模型） | `python main.py run-all` | 12/12 通过，Guard 更正 0 次，见 `examples/results/real_summary.md` |
| 验收用例（离线 Mock） | `python main.py run-all --mock` | 12/12 通过，见 `examples/results/mock_summary.md` |
| 单元测试与对账测试 | `python -m pytest -q` | 42 passed |
| 人工检查 Trace | 对照 `examples/runs/real/*/trace.md`，核对每一步的参数、返回和下一步动作是否一致 | 一致；发现的异常（case10 参数 JSON 格式错误后自行修正、case03/04 的多余调用）已写入 03-evaluation.md |

## 实际用时

约 6 小时。大部分时间花在理解题目和阅读代码上，其余用于配置环境、申请模型 Key、排查 GitHub 推送问题。

## 开发中发现并修正的问题

1. 草稿指纹最初包含“确认事项”的文字。真实模型每次措辞不同，会让重复提交变成“更新”而不是“去重”，因此改为只用“时段 + 是否待确认”。在 case06 中得到确认：第二次运行时确认事项由模型重新生成，结果仍是 `deduplicated`。
2. 保存失败的故障注入最初在业务校验之前计数，导致一次因冲突被拒的调用“吃掉”了注入的故障，因此改为通过校验后才注入。
3. 时段查询最初无法区分“被自己的草稿占用”，因此增加了 `held_by_own_draft` 状态。在 case06 中可以看到，模型正是根据 `19:00(held_by_own_draft:M01)` 选择了原时段。
