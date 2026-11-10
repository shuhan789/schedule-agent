# 运行记录：case05_risk_verified_pass

- 模式：**mock**（ScriptedLLM (离线 Mock，回放预设动作)）
- 请求：`REQ-005`  运行序号：1
- 上限：最多 15 轮模型调用 / 40 次工具调用

> 离线 Mock：动作序列是预先写好的回放，只验证流程，不代表真实模型决策。

| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |
|---|---|---|---|---|---|---|
| 1 | 1 | `read_material` | {"material_id": "M05"} | 《毕业季剪辑技巧》 bgm=unknown，字段完整 | 读取M05元数据 | `check_rules` |
| 2 | 2 | `check_rules` | {"material_id": "M05", "channel": "feed"} | verdict=needs_verification，命中: R03(needs_verification) | 审核M05 | `lookup_license` |
| 3 | 3 | `lookup_license` | {"material_id": "M05"} | TRK-305 授权状态=valid | M05背景音乐授权未知，补查版权库 | `check_rules` |
| 4 | 4 | `check_rules` | {"material_id": "M05", "channel": "feed"} | verdict=pass | 补查完成，重新审核 | `query_slots` |
| 5 | 5 | `query_slots` | {"channel": "feed", "date": "2026-11-12", "material_id": "M05"} | 空闲: ['10:00', '12:00', '19:00', '20:00']；占用: ['18:00(occupied:M90)', '21:00(occupied:M91)'] | 查询当天时段占用 | `save_draft` |
| 6 | 6 | `save_draft` | {"material_id": "M05", "channel": "feed", "date": "2026-11-12", "time": "19:00", "needs_confirmation": false, "confirmation_items": [], "note": ""} | created DRAFT-FB4F42DE 19:00 status=ready v1 | 保存M05 19:00草稿 | `submit_report` |
| 7 | 7 | `submit_report` | {"items": 1} | 提交最终结果 | 全部素材已有结论 | `（结束）` |

## 最终结果

- task_status: **completed**  模型已提交结果
- published: False

| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |
|---|---|---|---|---|---|---|---|
| M05 | approved | - | 19:00 | 19:00 | - | created DRAFT-FB4F42DE (ready) | draft_saved |

**总结**：M05补查授权有效，已保存19:00草稿（未发布）。

