# 运行记录：case08_save_failure

- 模式：**mock**（ScriptedLLM (离线 Mock，回放预设动作)）
- 请求：`REQ-008`  运行序号：1
- 上限：最多 15 轮模型调用 / 40 次工具调用

> 离线 Mock：动作序列是预先写好的回放，只验证流程，不代表真实模型决策。

| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |
|---|---|---|---|---|---|---|
| 1 | 1 | `read_material` | {"material_id": "M02"} | 《冬日vlog模板上新》 bgm=licensed，字段完整 | 读取M02元数据 | `check_rules` |
| 2 | 2 | `check_rules` | {"material_id": "M02", "channel": "feed"} | verdict=pass | 审核M02 | `query_slots` |
| 3 | 3 | `query_slots` | {"channel": "feed", "date": "2026-11-12", "material_id": "M02"} | 空闲: ['10:00', '12:00', '19:00', '20:00']；占用: ['18:00(occupied:M90)', '21:00(occupied:M91)'] | 查询当天时段占用 | `save_draft` |
| 4 | 4 | `save_draft` | {"material_id": "M02", "channel": "feed", "date": "2026-11-12", "time": "20:00", "needs_confirmation": false, "confirmation_items": [], "note": ""} | 失败 STORAGE_UNAVAILABLE: 草稿存储服务不可用，本次未保存（可重试） | 保存M02 20:00草稿 | `save_draft` |
| 5 | 5 | `save_draft` | {"material_id": "M02", "channel": "feed", "date": "2026-11-12", "time": "20:00", "needs_confirmation": false, "confirmation_items": [], "note": ""} | 失败 STORAGE_UNAVAILABLE: 草稿存储服务不可用，本次未保存（可重试） | 存储可重试，重试1次 | `submit_report` |
| 6 | 6 | `submit_report` | {"items": 1} | 提交最终结果 | 全部素材已有结论 | `（结束）` |

## 最终结果

- task_status: **partial_failed**  模型已提交结果
- published: False

| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |
|---|---|---|---|---|---|---|---|
| M02 | approved | - | 20:00 | 20:00 | - | 未保存: failed STORAGE_UNAVAILABLE | save_failed |

**总结**：M02审核通过，但草稿保存两次均失败（STORAGE_UNAVAILABLE），未保存。

