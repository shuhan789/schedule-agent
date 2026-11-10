# 运行记录：case06_duplicate_submit

- 模式：**real**（deepseek-chat @ https://api.deepseek.com）
- 请求：`REQ-002`  运行序号：2
- 上限：最多 15 轮模型调用 / 40 次工具调用

| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |
|---|---|---|---|---|---|---|
| 1 | 1 | `read_material` | {"material_id": "M01"} | 《小影AI一键成片教程》 bgm=owned，字段完整 | 读取 M01 元数据以确认字段完整性和基本信息 | `check_rules` |
| 2 | 1 | `check_rules` | {"material_id": "M01", "channel": "feed"} | verdict=pass | 按 feed 渠道规则审核 M01 是否可排期 | `query_slots` |
| 3 | 2 | `query_slots` | {"channel": "feed", "date": "2026-11-12", "material_id": "M01"} | 空闲: ['10:00', '12:00', '20:00']；占用: ['18:00(occupied:M90)', '19:00(held_by_own_draft:M01)', '21:00(occupied:M91)'] | 查询 2026-11-12 feed 渠道时段占用，确认 18:00 是否可用 | `save_draft` |
| 4 | 3 | `save_draft` | {"material_id": "M01", "channel": "feed", "date": "2026-11-12", "time": "19:00", "needs_confirmation": true, "confirmation_items": ["原定 18:00 已被占用（M90），建议改为 19:00，需用户确认"], "note": "M01 审核通过；18:00 被 M90 占用，按 flexible 规则改选同日最接近的空闲时段 19:00（该时段为 M01 自身已有草稿占用）。"} | deduplicated DRAFT-CF6562FB 19:00 status=pending_confirmation v1 | 18:00 被占用且素材为 flexible，保存 19:00 草稿并标记需用户确认 | `submit_report` |
| 5 | 4 | `submit_report` | {"items": 1} | 提交最终结果 | M01 已完成审核与草稿保存，需向用户汇报改期确认事项 | `（结束）` |

## 最终结果

- task_status: **needs_user_action**  模型已提交结果
- published: False

| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |
|---|---|---|---|---|---|---|---|
| M01 | approved | - | 18:00 | 19:00 | 原定 18:00 已被占用（M90），建议改为 19:00，需用户确认 | deduplicated DRAFT-CF6562FB (pending_confirmation) | draft_saved_pending_confirmation |

**总结**：M01 审核通过（无规则命中，BGM 为自有授权）。原定 2026-11-12 18:00 的 feed 时段已被 M90 占用，因素材为 flexible，已保存同日最接近的空闲时段 19:00 草稿（DRAFT-CF6562FB，状态 pending_confirmation，未发布），需用户确认改期。

