# 03 评估：测试预期、实际结果、失败与限制

## 评估方法

三层验证，互相补充：

| 层 | 内容 | 证明什么 | 不能证明什么 |
|---|---|---|---|
| 单元测试 `tests/test_tools.py` | 直接调用工具，验证硬约束 | 即使模型出错，越权/冲突/重复/虚报在系统层面不会发生 | 模型能否做出正确决策 |
| 对账测试 `tests/test_agent_and_guard.py` | 用脚本模拟“出错的模型”（谎称保存成功、说已发布、审核结论错误、不提交、参数非法、调用超限、接口报错） | Guard 与循环的兜底行为 | 同上 |
| 验收用例 `examples/cases/*.json` | 12 个场景，同一套自动核对分别用于 Mock 和真实模型 | Mock：管道正确；**真实模型：决策是否正确** | — |

每个用例除专属预期外，都检查三条不变量：**从未发布**、**草稿无时段冲突**、**报告的保存状态与存储一致**。

运行命令：

```bash
python -m pytest -q              # 42 个测试
python main.py run-all --mock    # 离线 Mock → examples/results/mock_summary.md
python main.py run-all           # 真实模型 → examples/results/real_summary.md
```

## 用例与验收点对照

| 用例 | 场景 | 覆盖验收点 | 关键预期 |
|---|---|---|---|
| [case01_normal](../examples/cases/case01_normal.json) | M02 要求 20:00，空闲 | 正常排期 | 草稿 20:00，无需确认，completed |
| [case02_slot_conflict](../examples/cases/case02_slot_conflict.json) | **参考实例**：M01 要求 18:00 已占用 | 时段冲突、确认边界 | 草稿时段 ≠ 18:00/21:00，待确认，needs_user_action |
| [case03_missing_info](../examples/cases/case03_missing_info.json) | M03 缺封面、时长 | 素材信息缺失 | needs_info，风险原因提到缺失字段，无草稿 |
| [case04_rule_risk_block](../examples/cases/case04_rule_risk_block.json) | M04 音乐授权未知、M06 含极限词 | 规则风险 | 对 M04 调用了补查；两者均 blocked，无草稿 |
| [case05_risk_verified_pass](../examples/cases/case05_risk_verified_pass.json) | M05 音乐授权未知，补查有效 | 规则风险、正常排期 | 调用补查后保存 19:00 草稿 |
| [case06_duplicate_submit](../examples/cases/case06_duplicate_submit.json) | 同一请求运行两次 | 重复提交 | 第二次 deduplicated，存储中仅 1 份草稿 |
| [case07_resubmit_after_slot_change](../examples/cases/case07_resubmit_after_slot_change.json) | 第二次运行前 19:00 被 M92 占用 | 时段冲突、重复提交 | 第二次 updated 到新时段，仍只有 1 份草稿，且不在 18:00/19:00 |
| [case08_save_failure](../examples/cases/case08_save_failure.json) | 存储持续不可用 | 保存失败、工具失败 | save_failed，partial_failed，无草稿 |
| [case09_tool_transient_failure](../examples/cases/case09_tool_transient_failure.json) | 时段查询首次超时 | 工具失败 | 重试后成功，completed |
| [case10_fixed_time_conflict](../examples/cases/case10_fixed_time_conflict.json) | M02 **固定** 18:00 已占用 | 时段冲突、确认边界 | 不保存，awaiting_confirmation |
| [case11_step_limit](../examples/cases/case11_step_limit.json) | 上限 3 轮 | 执行上限 | incomplete，原因含“上限” |
| [case12_batch](../examples/cases/case12_batch.json) | 4 个素材混合 | 综合 | 3 份草稿互不冲突，M01 待确认，M06 阻断 |

题目要求的“至少 3 组：正常、信息不足、工具失败”分别对应 case01、case03、case08/case09。

## 实际结果：离线 Mock

完整核对明细见 [examples/results/mock_summary.md](../examples/results/mock_summary.md)，逐步 Trace 见 `examples/runs/mock/<用例>/trace.md`。

- 12/12 用例通过，42/42 测试通过。
- Mock 只是回放预写动作，结果说明工具、循环、对账、Trace 与自动核对这条管道是正确的，**不说明模型决策效果**。
- 为确认核对本身有效，做过两次“故意改坏”的检查：去掉草稿去重后 case06 失败；去掉“改时间须待确认”校验后对应单元测试失败。

## 实际结果：真实模型

- 模型：`deepseek-chat`（DeepSeek 官方接口，temperature=0），运行日期 2026-11-10，每个用例运行 1 次
- 结果汇总：[examples/results/real_summary.md](../examples/results/real_summary.md)，**12/12 通过，Guard 更正 0 次**
- 逐步 Trace：`examples/runs/real/<用例>/trace.md`

Guard 更正为 0，说明模型在每个用例中提交的审核结论、草稿保存状态都与工具真实记录一致，没有出现“虚报保存成功”或“已发布”表述，不需要对账层兜底。

| 用例 | 结果 | 工具调用 | 观察（模型实际怎么做的） |
|---|---|---|---|
| [case01](../examples/runs/real/case01_normal/trace.md) | ✅ | 4 | 读取 → 审核 pass → 查时段确认 20:00 空闲 → 按原时间保存（created，无需确认） |
| [case02](../examples/runs/real/case02_slot_conflict/trace.md) | ✅ | 4 | 查时段发现 18:00 被 M90 占用，自行选择同日最接近的空闲时段 19:00，保存时 `needs_confirmation=true` 并写明“原定 18:00 已被占用，建议改为 19:00，需用户确认”；总结写明“仅草稿未发布” |
| [case03](../examples/runs/real/case03_missing_info/trace.md) | ✅ | 3 | 审核 needs_info 后未保存草稿，列出缺失的 duration_sec、cover_url。另外多查了一次时段，作为补齐后排期的参考（非必要，但无害） |
| [case04](../examples/runs/real/case04_rule_risk_block/trace.md) | ✅ | 7 | M04 返回 needs_verification → 调 lookup_license 得到 expired → 再次 check_rules 得到 block；M06 直接 block。两者都未保存。模型在拿到补查结果前，同一轮里提前查了一次 M04 的时段，属于多余调用 |
| [case05](../examples/runs/real/case05_risk_verified_pass/trace.md) | ✅ | 6 | M05 同样 needs_verification → 补查得到 valid → 重新审核 pass → 查时段 → 按 19:00 保存 |
| [case06](../examples/runs/real/case06_duplicate_submit/) | ✅ | 8 | 第二次运行时 query_slots 显示 `19:00(held_by_own_draft:M01)`，模型据此仍选 19:00 保存，返回 `deduplicated`，存储中仍只有 1 份草稿（v1） |
| [case07](../examples/runs/real/case07_resubmit_after_slot_change/) | ✅ | 8 | 第二次运行时 19:00 已被 M92 占用，模型改选 20:00，同一份草稿 `updated` 为 v2，19:00 不再保留 |
| [case08](../examples/runs/real/case08_save_failure/trace.md) | ✅ | 5 | 保存返回 STORAGE_UNAVAILABLE（可重试）→ 按提示只重试 1 次 → 仍失败后如实报告“草稿未能保存”，task_status=partial_failed |
| [case09](../examples/runs/real/case09_tool_transient_failure/trace.md) | ✅ | 5 | 时段查询首次超时 → 模型重试 → 成功后正常保存，completed |
| [case10](../examples/runs/real/case10_fixed_time_conflict/trace.md) | ✅ | 3 | 18:00 被占用且为 fixed，模型没有调用 save_draft，在结果中给出建议 19:00 并请求用户确认。**意外情况**：第一次 submit_report 的参数 JSON 格式错误，循环把解析错误作为观察返回，模型下一轮重新提交成功 |
| [case11](../examples/runs/real/case11_step_limit/trace.md) | ✅ | 6 | 模型每轮并行处理两个素材，第 3 轮查完时段后达到 3 轮上限，返回 incomplete 及原因“模型调用轮数达到上限 3” |
| [case12](../examples/runs/real/case12_batch/trace.md) | ✅ | 14 | 先为原时段空闲的 M05(19:00)、M02(20:00) 保存，再给 M01 找替代：18/19/20/21 点都已不可用，选 12:00 并在确认事项中解释“19:00、20:00 已分配给 M05、M02，故未选更接近的时段”；M06 阻断。3 份草稿互不冲突 |

### 两条执行路径对照

题目要求体现“模型根据不同工具结果调整动作”。以下三组对照中，用例输入结构相同，差异只来自工具返回：

**1. 补查结果不同 → 阻断 vs 继续排期**

| 步骤 | case04 · M04 | case05 · M05 |
|---|---|---|
| check_rules | needs_verification（R03 授权未知） | needs_verification（R03 授权未知） |
| lookup_license | **expired** | **valid** |
| 再次 check_rules | block | pass |
| 后续动作 | 不查时段、不保存，报告阻断原因 | query_slots → save_draft 19:00 |

**2. 时间要求的灵活度不同 → 改时段保存 vs 不保存、请求确认**

| 步骤 | case02 · M01（flexible） | case10 · M02（fixed） |
|---|---|---|
| query_slots | 18:00 被 M90 占用 | 18:00 被 M90 占用 |
| 后续动作 | save_draft 19:00，needs_confirmation=true | **不调用 save_draft**，直接 submit_report 请求确认 |
| 最终状态 | draft_saved_pending_confirmation | awaiting_confirmation |

**3. 重复提交时占用情况不同 → 去重 vs 更新同一份草稿**

| 步骤 | case06 第 2 次运行 | case07 第 2 次运行 |
|---|---|---|
| query_slots | 19:00 = held_by_own_draft（自己的草稿） | 19:00 = occupied（被 M92 占用） |
| save_draft | 19:00 → **deduplicated** | 20:00 → **updated（v2）** |
| 存储中 M01 草稿数 | 1 | 1 |

另外，case08 与 case09 对比了工具失败后的两种结局：持续失败时重试 1 次后如实报告失败；临时失败时重试后继续完成任务。

### 失败与异常分析

12 个用例的自动核对全部通过，没有失败用例。但逐条阅读 Trace 发现以下不完美之处，记录如下：

1. **参数格式错误（case10）**：模型第一次调用 submit_report 时生成的 JSON 不合法。循环没有崩溃，而是把错误信息作为工具结果返回，模型下一轮自行修正。这说明“参数解析失败也当作观察返回”的设计是必要的；但它也多消耗了一轮，如果步数上限设得很紧，可能因此变成 incomplete。
2. **多余调用（case03、case04）**：模型在已经不需要排期时仍查询了时段。没有造成错误结果，但浪费调用次数。可以在提示词中说明“审核未通过时无需查询时段”，或者接受这种为用户提供参考信息的行为。
3. **调用顺序上的“抢跑”（case04）**：模型在同一轮里并行发起 lookup_license 和 query_slots，即在拿到补查结果前就开始查时段。最终结论仍正确，因为保存草稿前工具层会重新审核。
4. **只运行了一次**：上述结论来自单次运行，不能证明每次运行都稳定通过，见“已知限制”第 1 条。

## 已知限制

1. **真实模型结果有波动**：temperature=0 仍不保证每次相同。只运行一次的结果不能代表稳定性；没有做多次运行的统计。
2. **Guard 只更正、不重来**：模型报告与工具记录冲突时，最终结果会被更正，但不会让模型重新执行。
3. **替代时段只在同一天内找**，不支持跨天改期或跨渠道；当天无空闲时段时只能请求用户决定。
4. **“最接近”的替代时段由模型判断**，工具层不强制；如果模型选了较远的空闲时段，核对不会判失败（只核对不冲突且待确认）。
5. **存储为单进程 JSON 文件**，没有并发控制；仅适合本演示。
6. **规则是简化的合成规则**：极限词用字符串包含匹配，会误判也会漏判（例如同音、变体字）。
7. **越权表述检测基于关键词**，只覆盖“已发布 / 已上线 / 发布成功”等常见说法。
8. **Mock 不能随数据变化**：修改 data/ 后，Mock 脚本可能与新数据不符，此时应以真实模型运行为准。
