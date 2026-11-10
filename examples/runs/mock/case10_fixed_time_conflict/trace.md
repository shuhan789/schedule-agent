# 运行记录：case10_fixed_time_conflict

- 模式：**mock**（ScriptedLLM (离线 Mock，回放预设动作)）
- 请求：`REQ-010`  运行序号：1
- 上限：最多 15 轮模型调用 / 40 次工具调用

> 离线 Mock：动作序列是预先写好的回放，只验证流程，不代表真实模型决策。

| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |
|---|---|---|---|---|---|---|
| 1 | 1 | `read_material` | {"material_id": "M02"} | 《冬日vlog模板上新》 bgm=licensed，字段完整 | 读取M02元数据 | `check_rules` |
| 2 | 2 | `check_rules` | {"material_id": "M02", "channel": "feed"} | verdict=pass | 审核M02 | `query_slots` |
| 3 | 3 | `query_slots` | {"channel": "feed", "date": "2026-11-12", "material_id": "M02"} | 空闲: ['10:00', '12:00', '19:00', '20:00']；占用: ['18:00(occupied:M90)', '21:00(occupied:M91)'] | 查询当天时段占用 | `submit_report` |
| 4 | 4 | `submit_report` | {"items": 1} | 提交最终结果 | 全部素材已有结论 | `（结束）` |

## 最终结果

- task_status: **needs_user_action**  模型已提交结果
- published: False

| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |
|---|---|---|---|---|---|---|---|
| M02 | approved | - | 18:00 | 19:00 | 用户要求固定18:00发布，该时段已被M90占用；可选19:00/20:00，是否同意改期？ | 未保存: not_attempted  | awaiting_confirmation |

**总结**：M02固定时段冲突，未保存草稿，等待用户决定。

