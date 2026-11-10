# 运行记录：case09_tool_transient_failure

- 模式：**mock**（ScriptedLLM (离线 Mock，回放预设动作)）
- 请求：`REQ-009`  运行序号：1
- 上限：最多 15 轮模型调用 / 40 次工具调用

> 离线 Mock：动作序列是预先写好的回放，只验证流程，不代表真实模型决策。

| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |
|---|---|---|---|---|---|---|
| 1 | 1 | `read_material` | {"material_id": "M02"} | 《冬日vlog模板上新》 bgm=licensed，字段完整 | 读取M02元数据 | `check_rules` |
| 2 | 2 | `check_rules` | {"material_id": "M02", "channel": "feed"} | verdict=pass | 审核M02 | `query_slots` |
| 3 | 3 | `query_slots` | {"channel": "feed", "date": "2026-11-12", "material_id": "M02"} | 失败 SCHEDULE_SERVICE_TIMEOUT: query_slots 暂时不可用（注入故障）（可重试） | 查询当天时段占用 | `query_slots` |
| 4 | 4 | `query_slots` | {"channel": "feed", "date": "2026-11-12", "material_id": "M02"} | 空闲: ['10:00', '12:00', '19:00', '20:00']；占用: ['18:00(occupied:M90)', '21:00(occupied:M91)'] | 上次超时且可重试，重试 | `save_draft` |
| 5 | 5 | `save_draft` | {"material_id": "M02", "channel": "feed", "date": "2026-11-12", "time": "20:00", "needs_confirmation": false, "confirmation_items": [], "note": ""} | created DRAFT-FB7A1E15 20:00 status=ready v1 | 保存M02 20:00草稿 | `submit_report` |
| 6 | 6 | `submit_report` | {"items": 1} | 提交最终结果 | 全部素材已有结论 | `（结束）` |

## 最终结果

- task_status: **completed**  模型已提交结果
- published: False

| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |
|---|---|---|---|---|---|---|---|
| M02 | approved | - | 20:00 | 20:00 | - | created DRAFT-FB7A1E15 (ready) | draft_saved |

**总结**：M02已保存20:00草稿（未发布）。

