# 运行记录：case12_batch

- 模式：**real**（deepseek-chat @ https://api.deepseek.com）
- 请求：`REQ-012`  运行序号：1
- 上限：最多 20 轮模型调用 / 60 次工具调用

| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |
|---|---|---|---|---|---|---|
| 1 | 1 | `read_material` | {"material_id": "M01"} | 《小影AI一键成片教程》 bgm=owned，字段完整 | 读取 M01 元数据以确认字段完整性和审核所需信息 | `read_material` |
| 2 | 1 | `read_material` | {"material_id": "M05"} | 《毕业季剪辑技巧》 bgm=unknown，字段完整 | 读取 M05 元数据以确认字段完整性和审核所需信息 | `read_material` |
| 3 | 1 | `read_material` | {"material_id": "M02"} | 《冬日vlog模板上新》 bgm=licensed，字段完整 | 读取 M02 元数据以确认字段完整性和审核所需信息 | `read_material` |
| 4 | 1 | `read_material` | {"material_id": "M06"} | 《全网第一的卡点模板》 bgm=owned，字段完整 | 读取 M06 元数据以确认字段完整性和审核所需信息 | `check_rules` |
| 5 | 2 | `check_rules` | {"material_id": "M01", "channel": "feed"} | verdict=pass | M01 元数据完整，按 feed 渠道规则审核 | `check_rules` |
| 6 | 2 | `check_rules` | {"material_id": "M05", "channel": "feed"} | verdict=needs_verification，命中: R03(needs_verification) | M05 背景音乐授权未知，先按 feed 规则审核看结论 | `check_rules` |
| 7 | 2 | `check_rules` | {"material_id": "M02", "channel": "feed"} | verdict=pass | M02 元数据完整，按 feed 渠道规则审核 | `check_rules` |
| 8 | 2 | `check_rules` | {"material_id": "M06", "channel": "feed"} | verdict=block，命中: R02(block) | M06 元数据完整，按 feed 渠道规则审核 | `lookup_license` |
| 9 | 3 | `lookup_license` | {"material_id": "M05"} | TRK-305 授权状态=valid | check_rules 返回 needs_verification，需到版权库补查 TRK-305 授权状态 | `query_slots` |
| 10 | 3 | `query_slots` | {"channel": "feed", "date": "2026-11-12"} | 空闲: ['10:00', '12:00', '19:00', '20:00']；占用: ['18:00(occupied:M90)', '21:00(occupied:M91)'] | 查询 feed 渠道 2026-11-12 各时段占用，为可排期素材选时段 | `check_rules` |
| 11 | 4 | `check_rules` | {"channel": "feed", "material_id": "M05"} | verdict=pass | 已补查 TRK-305 授权有效，重新审核 M05 获取最终结论 | `save_draft` |
| 12 | 5 | `save_draft` | {"material_id": "M05", "channel": "feed", "date": "2026-11-12", "time": "19:00", "needs_confirmation": false} | created DRAFT-FB4F42DE 19:00 status=ready v1 | M05 审核通过，用户要求的 19:00 空闲，按原时间保存草稿 | `save_draft` |
| 13 | 5 | `save_draft` | {"material_id": "M02", "channel": "feed", "date": "2026-11-12", "time": "20:00", "needs_confirmation": false} | created DRAFT-FB7A1E15 20:00 status=ready v1 | M02 审核通过，用户要求的 20:00 空闲，按原时间保存草稿 | `save_draft` |
| 14 | 6 | `save_draft` | {"channel": "feed", "confirmation_items": ["原定 18:00 已被占用（M90），建议改为 12:00，需用户确认", "19:00 已分配给 M05、20:00 已分配给 M02，故未选更接近的时段"], "date": "2026-11-12", "material_id": "M01", "needs_confirmation": true, "time": "12:00"} | created DRAFT-CF6562FB 12:00 status=pending_confirmation v1 | M01 审核通过但原定 18:00 被占用，flexible 下选同日最接近的空闲时段 12:00 并标记需确认 | `submit_report` |
| 15 | 7 | `submit_report` | {"items": 4} | 提交最终结果 | 四个素材均已有明确结论，草稿保存结果已确认，提交结构化报告结束任务 | `（结束）` |

## 最终结果

- task_status: **needs_user_action**  模型已提交结果
- published: False

| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |
|---|---|---|---|---|---|---|---|
| M01 | approved | - | 18:00 | 12:00 | 原定 18:00 已被占用（M90），建议改为 12:00，需用户确认；19:00 已分配给 M05、20:00 已分配给 M02，故未选更接近的时段 | created DRAFT-CF6562FB (pending_confirmation) | draft_saved_pending_confirmation |
| M05 | approved | - | 19:00 | 19:00 | - | created DRAFT-FB4F42DE (ready) | draft_saved |
| M02 | approved | - | 20:00 | 20:00 | - | created DRAFT-FB7A1E15 (ready) | draft_saved |
| M06 | blocked | 标题/描述含广告法极限词: 全网第一，需修改文案 | 12:00 | - | - | 未保存: not_attempted  | blocked |

**总结**：共处理 4 个素材：M05、M02 审核通过并按原要求时段（19:00、20:00）保存草稿；M01 审核通过但原定 18:00 已被 M90 占用，已按 flexible 规则改选同日最接近的空闲时段 12:00 保存草稿并标记需用户确认；M06 因标题含极限词“全网第一”被阻断，未保存草稿，需修改文案后重审。所有草稿均未发布。

