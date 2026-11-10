# 运行记录：case08_save_failure

- 模式：**real**（deepseek-chat @ https://api.deepseek.com）
- 请求：`REQ-008`  运行序号：1
- 上限：最多 15 轮模型调用 / 40 次工具调用

| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |
|---|---|---|---|---|---|---|
| 1 | 1 | `read_material` | {"material_id": "M02"} | 《冬日vlog模板上新》 bgm=licensed，字段完整 | 读取 M02 元数据以确认字段完整性和素材内容 | `check_rules` |
| 2 | 1 | `check_rules` | {"material_id": "M02", "channel": "feed"} | verdict=pass | 按 feed 渠道规则审核 M02 是否可排期 | `query_slots` |
| 3 | 2 | `query_slots` | {"channel": "feed", "date": "2026-11-12", "material_id": "M02"} | 空闲: ['10:00', '12:00', '19:00', '20:00']；占用: ['18:00(occupied:M90)', '21:00(occupied:M91)'] | 查询 2026-11-12 feed 渠道时段占用，确认 20:00 是否可用 | `save_draft` |
| 4 | 3 | `save_draft` | {"material_id": "M02", "channel": "feed", "date": "2026-11-12", "time": "20:00", "needs_confirmation": false, "note": "M02 审核通过，按用户要求 20:00 排期 feed 渠道，时段空闲无冲突。"} | 失败 STORAGE_UNAVAILABLE: 草稿存储服务不可用，本次未保存（可重试） | 审核通过且 20:00 空闲，按用户原定时间保存草稿 | `save_draft` |
| 5 | 4 | `save_draft` | {"channel": "feed", "date": "2026-11-12", "material_id": "M02", "needs_confirmation": false, "note": "M02 审核通过，按用户要求 20:00 排期 feed 渠道，时段空闲无冲突（重试保存）。", "time": "20:00"} | 失败 STORAGE_UNAVAILABLE: 草稿存储服务不可用，本次未保存（可重试） | 上次保存因存储不可用失败，按规则重试一次 | `submit_report` |
| 6 | 5 | `submit_report` | {"items": 1} | 提交最终结果 | M02 已有审核结论与可用时段，但草稿保存两次失败，需如实上报未完成状态 | `（结束）` |

## 最终结果

- task_status: **partial_failed**  模型已提交结果
- published: False

| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |
|---|---|---|---|---|---|---|---|
| M02 | approved | - | 20:00 | 20:00 | - | 未保存: failed STORAGE_UNAVAILABLE | save_failed |

**总结**：M02 审核通过（feed 渠道，无规则命中），2026-11-12 20:00 时段空闲、与用户要求一致，无需改期。但 save_draft 连续两次返回 STORAGE_UNAVAILABLE（可重试错误），草稿未能保存，需存储恢复后重试。未发布任何内容。

