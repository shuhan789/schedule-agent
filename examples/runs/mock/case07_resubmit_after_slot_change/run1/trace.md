# 运行记录：case07_resubmit_after_slot_change

- 模式：**mock**（ScriptedLLM (离线 Mock，回放预设动作)）
- 请求：`REQ-002`  运行序号：1
- 上限：最多 15 轮模型调用 / 40 次工具调用

> 离线 Mock：动作序列是预先写好的回放，只验证流程，不代表真实模型决策。

| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |
|---|---|---|---|---|---|---|
| 1 | 1 | `read_material` | {"material_id": "M01"} | 《小影AI一键成片教程》 bgm=owned，字段完整 | 读取M01元数据 | `check_rules` |
| 2 | 2 | `check_rules` | {"material_id": "M01", "channel": "feed"} | verdict=pass | 审核M01 | `query_slots` |
| 3 | 3 | `query_slots` | {"channel": "feed", "date": "2026-11-12", "material_id": "M01"} | 空闲: ['10:00', '12:00', '19:00', '20:00']；占用: ['18:00(occupied:M90)', '21:00(occupied:M91)'] | 查询当天时段占用 | `save_draft` |
| 4 | 4 | `save_draft` | {"material_id": "M01", "channel": "feed", "date": "2026-11-12", "time": "19:00", "needs_confirmation": true, "confirmation_items": ["原定18:00已被M90占用，建议改为19:00，需用户确认"], "note": ""} | created DRAFT-CF6562FB 19:00 status=pending_confirmation v1 | 18:00被占用，选最近空闲19:00并标待确认 | `submit_report` |
| 5 | 5 | `submit_report` | {"items": 1} | 提交最终结果 | 全部素材已有结论 | `（结束）` |

## 最终结果

- task_status: **needs_user_action**  模型已提交结果
- published: False

| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |
|---|---|---|---|---|---|---|---|
| M01 | approved | - | 18:00 | 19:00 | 原定18:00已被M90占用，建议改为19:00，需用户确认 | created DRAFT-CF6562FB (pending_confirmation) | draft_saved_pending_confirmation |

**总结**：M01审核通过；18:00已被占用，草稿建议19:00，待用户确认（仅草稿，未发布）。

