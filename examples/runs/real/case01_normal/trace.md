# 运行记录：case01_normal

- 模式：**real**（deepseek-chat @ https://api.deepseek.com）
- 请求：`REQ-001`  运行序号：1
- 上限：最多 15 轮模型调用 / 40 次工具调用

| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |
|---|---|---|---|---|---|---|
| 1 | 1 | `read_material` | {"material_id": "M02"} | 《冬日vlog模板上新》 bgm=licensed，字段完整 | 读取 M02 素材元数据，确认字段完整性与基本信息 | `check_rules` |
| 2 | 1 | `check_rules` | {"material_id": "M02", "channel": "feed"} | verdict=pass | 按 feed 渠道规则审核 M02 是否可排期 | `query_slots` |
| 3 | 2 | `query_slots` | {"channel": "feed", "date": "2026-11-12", "material_id": "M02"} | 空闲: ['10:00', '12:00', '19:00', '20:00']；占用: ['18:00(occupied:M90)', '21:00(occupied:M91)'] | 查询 2026-11-12 feed 渠道时段占用，确认 20:00 是否可用 | `save_draft` |
| 4 | 3 | `save_draft` | {"material_id": "M02", "channel": "feed", "date": "2026-11-12", "time": "20:00", "needs_confirmation": false, "note": "M02 审核通过，按用户要求 20:00 排期，该时段空闲。"} | created DRAFT-FB7A1E15 20:00 status=ready v1 | 审核通过且 20:00 时段空闲，按用户原定时间保存草稿 | `submit_report` |
| 5 | 4 | `submit_report` | {"items": 1} | 提交最终结果 | M02 已完成审核与排期草稿保存，提交结构化结果 | `（结束）` |

## 最终结果

- task_status: **completed**  模型已提交结果
- published: False

| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |
|---|---|---|---|---|---|---|---|
| M02 | approved | - | 20:00 | 20:00 | - | created DRAFT-FB7A1E15 (ready) | draft_saved |

**总结**：M02（冬日vlog模板上新）审核通过，2026-11-12 feed 渠道 20:00 时段空闲，已按用户要求保存排期草稿 DRAFT-FB7A1E15（仅草稿，未发布），无需用户确认。

