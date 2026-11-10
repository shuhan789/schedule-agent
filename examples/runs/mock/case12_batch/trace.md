# 运行记录：case12_batch

- 模式：**mock**（ScriptedLLM (离线 Mock，回放预设动作)）
- 请求：`REQ-012`  运行序号：1
- 上限：最多 20 轮模型调用 / 60 次工具调用

> 离线 Mock：动作序列是预先写好的回放，只验证流程，不代表真实模型决策。

| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |
|---|---|---|---|---|---|---|
| 1 | 1 | `read_material` | {"material_id": "M01"} | 《小影AI一键成片教程》 bgm=owned，字段完整 | 读取M01元数据 | `read_material` |
| 2 | 1 | `read_material` | {"material_id": "M05"} | 《毕业季剪辑技巧》 bgm=unknown，字段完整 | 读取M05元数据 | `read_material` |
| 3 | 1 | `read_material` | {"material_id": "M02"} | 《冬日vlog模板上新》 bgm=licensed，字段完整 | 读取M02元数据 | `read_material` |
| 4 | 1 | `read_material` | {"material_id": "M06"} | 《全网第一的卡点模板》 bgm=owned，字段完整 | 读取M06元数据 | `check_rules` |
| 5 | 2 | `check_rules` | {"material_id": "M01", "channel": "feed"} | verdict=pass | 审核M01 | `check_rules` |
| 6 | 2 | `check_rules` | {"material_id": "M05", "channel": "feed"} | verdict=needs_verification，命中: R03(needs_verification) | 审核M05 | `check_rules` |
| 7 | 2 | `check_rules` | {"material_id": "M02", "channel": "feed"} | verdict=pass | 审核M02 | `check_rules` |
| 8 | 2 | `check_rules` | {"material_id": "M06", "channel": "feed"} | verdict=block，命中: R02(block) | 审核M06 | `lookup_license` |
| 9 | 3 | `lookup_license` | {"material_id": "M05"} | TRK-305 授权状态=valid | M05背景音乐授权未知，补查版权库 | `check_rules` |
| 10 | 4 | `check_rules` | {"material_id": "M05", "channel": "feed"} | verdict=pass | 补查完成，重新审核 | `query_slots` |
| 11 | 5 | `query_slots` | {"channel": "feed", "date": "2026-11-12"} | 空闲: ['10:00', '12:00', '19:00', '20:00']；占用: ['18:00(occupied:M90)', '21:00(occupied:M91)'] | 查询当天时段占用 | `save_draft` |
| 12 | 6 | `save_draft` | {"material_id": "M05", "channel": "feed", "date": "2026-11-12", "time": "19:00", "needs_confirmation": false, "confirmation_items": [], "note": ""} | created DRAFT-FB4F42DE 19:00 status=ready v1 | 先满足要求时段空闲的素材 | `save_draft` |
| 13 | 6 | `save_draft` | {"material_id": "M02", "channel": "feed", "date": "2026-11-12", "time": "20:00", "needs_confirmation": false, "confirmation_items": [], "note": ""} | created DRAFT-FB7A1E15 20:00 status=ready v1 | 保存M02 20:00草稿 | `query_slots` |
| 14 | 7 | `query_slots` | {"channel": "feed", "date": "2026-11-12"} | 空闲: ['10:00', '12:00']；占用: ['18:00(occupied:M90)', '19:00(held_by_draft:M05)', '20:00(held_by_draft:M02)', '21:00(occupied:M91)'] | M05/M02已占用19:00/20:00，重新查询为M01找替代时段 | `save_draft` |
| 15 | 8 | `save_draft` | {"material_id": "M01", "channel": "feed", "date": "2026-11-12", "time": "12:00", "needs_confirmation": true, "confirmation_items": ["原定18:00已被M90占用，19:00/20:00已分配给M05/M02，建议12:00，需用户确认"], "note": ""} | created DRAFT-CF6562FB 12:00 status=pending_confirmation v1 | 剩余空闲10:00/12:00，选更接近18:00的12:00 | `submit_report` |
| 16 | 9 | `submit_report` | {"items": 4} | 提交最终结果 | 全部素材已有结论 | `（结束）` |

## 最终结果

- task_status: **needs_user_action**  模型已提交结果
- published: False

| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |
|---|---|---|---|---|---|---|---|
| M01 | approved | - | 18:00 | 12:00 | 原定18:00已被M90占用，19:00/20:00已分配给M05/M02，建议12:00，需用户确认；原定18:00已被占用，建议12:00，需用户确认 | created DRAFT-CF6562FB (pending_confirmation) | draft_saved_pending_confirmation |
| M05 | approved | - | 19:00 | 19:00 | - | created DRAFT-FB4F42DE (ready) | draft_saved |
| M02 | approved | - | 20:00 | 20:00 | - | created DRAFT-FB7A1E15 (ready) | draft_saved |
| M06 | blocked | 标题/描述含广告法极限词: 全网第一，需修改文案 | 12:00 | - | - | 未保存: not_attempted  | blocked |

**总结**：3个草稿已保存（M01待确认），M06被阻断。均未发布。

