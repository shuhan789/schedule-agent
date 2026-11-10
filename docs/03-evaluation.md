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

> 【待你运行后填写】运行 `python main.py run-all` 后，把下表补全，并据实写下观察。不要照抄预期。

- 模型：`deepseek-chat`（运行日期：____）
- 结果汇总：[examples/results/real_summary.md](../examples/results/real_summary.md)
- 逐步 Trace：`examples/runs/real/<用例>/trace.md`

| 用例 | 结果 | 工具调用次数 | Guard 更正 | 观察（模型实际怎么做的） |
|---|---|---|---|---|
| case01 | | | | |
| case02 | | | | 例：先 query_slots 发现 18:00 被 M90 占用，选 19:00 并标待确认 |
| case03 | | | | |
| case04 | | | | |
| case05 | | | | |
| case06 | | | | |
| case07 | | | | |
| case08 | | | | |
| case09 | | | | |
| case10 | | | | |
| case11 | | | | |
| case12 | | | | |

**两条执行路径对照**（题目要求体现模型根据不同工具结果调整动作）。建议在真实 Trace 中引用以下几组：

1. case04 与 case05：同为“授权未知”，补查返回 expired → 阻断；返回 valid → 继续排期。
2. case02 与 case10：同为 18:00 被占用，flexible → 改时段并保存待确认；fixed → 不保存、请求确认。
3. case06 与 case07 的第二次运行：时段未变 → deduplicated；时段被占 → 改选并 updated。

**失败用例分析**：【如有失败，写清楚失败的是哪条核对、Trace 里模型做了什么、原因判断（提示词？工具描述？预期过严？）以及你改了什么、改后结果。】

## 已知限制

1. **真实模型结果有波动**：temperature=0 仍不保证每次相同。只运行一次的结果不能代表稳定性；没有做多次运行的统计。
2. **Guard 只更正、不重来**：模型报告与工具记录冲突时，最终结果会被更正，但不会让模型重新执行。
3. **替代时段只在同一天内找**，不支持跨天改期或跨渠道；当天无空闲时段时只能请求用户决定。
4. **“最接近”的替代时段由模型判断**，工具层不强制；如果模型选了较远的空闲时段，核对不会判失败（只核对不冲突且待确认）。
5. **存储为单进程 JSON 文件**，没有并发控制；仅适合本演示。
6. **规则是简化的合成规则**：极限词用字符串包含匹配，会误判也会漏判（例如同音、变体字）。
7. **越权表述检测基于关键词**，只覆盖“已发布 / 已上线 / 发布成功”等常见说法。
8. **Mock 不能随数据变化**：修改 data/ 后，Mock 脚本可能与新数据不符，此时应以真实模型运行为准。
