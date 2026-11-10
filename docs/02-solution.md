# 02 方案：调用流程、动态决策、技术取舍

## 整体结构

```
用户请求(JSON)
   │
   ▼
┌────────────── ReAct 循环 (agent.py) ──────────────┐
│  模型 ──选择工具+参数+reason──▶ 工具 (tools.py)    │
│   ▲                               │               │
│   └──────── 工具结果(观察) ◀──────┘               │
│  直到模型调用 submit_report，或达到步数/调用上限   │
└───────────────────────┬───────────────────────────┘
                        ▼
              Guard 对账 (guard.py)
     以工具记录为准，更正模型报告中的不实之处
                        ▼
          最终结果 + Trace (examples/runs/...)
```

职责划分是本方案的核心：

| 层 | 负责 | 不负责 |
|---|---|---|
| 模型 | 决定下一步调用哪个工具、选哪个替代时段、是否补查、是否重试、何时结束 | 保证约束不被破坏 |
| 工具层 | 硬约束：没有发布接口；save_draft 拒绝改日期、改 fixed 时段、未审核通过、时段冲突、改时间不标待确认 | 决策 |
| Guard | 以工具真实记录为准生成最终状态，更正“虚报保存成功”“已发布”等表述 | 替模型决策 |

这样即使模型出错，越权发布和虚报保存成功这两个关键缺陷在系统层面也不会出现；同时决策仍完全由模型完成。

## 工具

| 工具 | 作用 | 典型返回 |
|---|---|---|
| read_material | 读素材元数据 | 字段、`missing_fields` |
| check_rules | 按规则审核 | `verdict`: pass / needs_info / needs_verification / block，及命中规则 |
| lookup_license | 补查背景音乐授权 | `license_status`: valid / expired / not_found |
| query_slots | 查时段占用 | 每个时段状态（free / occupied / held_by_draft / held_by_own_draft） |
| save_draft | 保存草稿 | `action`: created / updated / deduplicated；或 `error_code` + `retryable` |
| submit_report | 提交最终结果并结束 | — |

每个工具都要求模型填写 `reason`（一句话依据），写入 Trace 的“决策依据”列。这满足“记录简要决策依据，但无需提交内部思维过程”的要求。

## 动态决策点

循环代码中没有任何业务分支，下面的选择都由模型根据工具返回做出（提示词只说明目标和边界，不规定调用顺序）：

| 观察到的结果 | 模型可选动作 | 对应用例 |
|---|---|---|
| check_rules = needs_verification | 调 lookup_license 补查 → 再次 check_rules | case04、case05 |
| 补查结果 expired | 阻断，不排期 | case04 |
| 补查结果 valid | 继续查时段、保存 | case05 |
| check_rules = needs_info | 不保存，列缺失字段，请运营补充 | case03 |
| check_rules = block | 阻断，说明风险 | case04 |
| 要求时段被占用 + flexible | 选替代空闲时段，标记待确认后保存 | case02、case07 |
| 要求时段被占用 + fixed | 不改时间、不保存，给出可选时段请求确认 | case10 |
| save_draft = SLOT_CONFLICT | 重新查询，改选时段 | case12（真实模型可能触发） |
| save_draft = CONFIRMATION_REQUIRED | 补上待确认标记重新保存 | 工具层兜底 |
| 工具 retryable 错误 | 重试一次；仍失败如实报告 | case08、case09 |
| save_draft = deduplicated | 视为正常，不重复创建 | case06 |

**同一规则、不同工具结果走出不同路径**的对照：case04（M04 补查 expired → 阻断）与 case05（M05 补查 valid → 排期）；case02（flexible → 改 19:00 待确认并保存）与 case10（fixed → 不保存、请求确认）；case08（保存一直失败 → 报告失败）与 case09（查询失败一次 → 重试后成功）。

## 防重复设计

- 草稿主键 = `素材|渠道|日期`，`draft_id` 由主键哈希得出，同一素材同一天在同一渠道永远只有一份草稿。
- 内容指纹 = `(时段, 是否待确认)`。指纹相同 → `deduplicated`，不写入；指纹不同 → 原地 `updated`，`version+1`。
- 指纹**不包含**说明文字和确认事项的措辞。最初的版本包含了，但真实模型每次措辞不同，会让“相同请求”被当作新提交。
- 占用变化后重提（审核要点中的“更换占用时段并重复提交”）：原草稿时段被他人占用 → 模型改选新时段 → 同一份草稿更新为 v2，旧时段自动释放（case07）。
- `query_slots` 传入 `material_id` 时，素材自己的草稿标为 `held_by_own_draft`，避免模型把自己的草稿误认为冲突。

## 执行上限

- `max_steps`（默认 15）：模型调用轮数上限；`max_tool_calls`（默认 40）：工具调用次数上限。
- 触发时返回 `task_status = incomplete`，`status_reason` 写明哪个上限；已保存的草稿仍按工具记录如实列出（测试 `test_partial_progress_survives_limit`）。
- 模型连续两次只回复文字、不调用 submit_report，同样返回 incomplete。

## 技术取舍

| 选择 | 理由 | 代价 |
|---|---|---|
| 原生实现循环，不用 LangGraph / ADK 等框架 | 循环本身不到 100 行；直接用 OpenAI 兼容 function calling，任何兼容厂商都能接；评审能直接读懂每一步 | 没有框架自带的可视化、持久化、并发 |
| 约束放在工具层，而不只靠提示词 | 提示词约束对模型是“建议”，工具层约束是“不可能违反”；关键缺陷必须不可能发生 | 部分规则在提示词和工具层各写一遍 |
| Guard 对账 | 模型的总结可能与事实不符；用户看到的状态必须以工具记录为准 | 模型报告与工具记录冲突时只能更正，无法让模型重新思考 |
| 结构化 submit_report 结束 | 结果可被程序核对，便于自动化评估 | 模型偶尔会忘记调用，需要一次提醒 |
| 草稿存 JSON 文件 | 无需数据库，评审可直接打开查看；原子替换写入 | 不支持并发写入 |
| Mock 采用“回放动作”而非规则策略 | 规则策略本身就是固定条件分支，容易与真实决策混淆；回放更诚实地表明“只测管道” | 改了数据后 Mock 脚本可能不再适用 |
| 自动核对同时用于 Mock 与真实模型 | 真实模型结果也能得到“预期 vs 实际”的客观结论 | 预期必须写得与具体措辞无关（只核对状态、时段、存储） |
| temperature = 0 | 尽量让真实运行可复现 | 仍不能保证完全一致 |

## 依赖

- `openai`（≥1.40）：仅用其 Chat Completions 客户端访问 OpenAI 兼容接口，承担 HTTP 请求与 function calling 消息格式。
- `python-dotenv`：读取 `.env`。
- `pytest`：测试。

未使用 Agent 框架。
