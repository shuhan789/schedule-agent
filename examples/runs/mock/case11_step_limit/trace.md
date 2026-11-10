# 运行记录：case11_step_limit

- 模式：**mock**（ScriptedLLM (离线 Mock，回放预设动作)）
- 请求：`REQ-011`  运行序号：1
- 上限：最多 3 轮模型调用 / 40 次工具调用

> 离线 Mock：动作序列是预先写好的回放，只验证流程，不代表真实模型决策。

| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |
|---|---|---|---|---|---|---|
| 1 | 1 | `read_material` | {"material_id": "M01"} | 《小影AI一键成片教程》 bgm=owned，字段完整 | 读取M01元数据 | `read_material` |
| 2 | 1 | `read_material` | {"material_id": "M02"} | 《冬日vlog模板上新》 bgm=licensed，字段完整 | 读取M02元数据 | `check_rules` |
| 3 | 2 | `check_rules` | {"material_id": "M01", "channel": "feed"} | verdict=pass | 审核M01 | `check_rules` |
| 4 | 2 | `check_rules` | {"material_id": "M02", "channel": "feed"} | verdict=pass | 审核M02 | `query_slots` |
| 5 | 3 | `query_slots` | {"channel": "feed", "date": "2026-11-12"} | 空闲: ['10:00', '12:00', '19:00', '20:00']；占用: ['18:00(occupied:M90)', '21:00(occupied:M91)'] | 查询当天时段占用 | `limit_reached` |
| 6 | 3 | `limit_reached` | {} | 模型调用轮数达到上限 3 |  | `（结束）` |

## 最终结果

- task_status: **incomplete**  未完成：模型调用轮数达到上限 3
- published: False

| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |
|---|---|---|---|---|---|---|---|
| M01 | approved | - | 18:00 | - | - | 未保存: not_attempted  | unresolved |
| M02 | approved | - | 20:00 | - | - | 未保存: not_attempted  | unresolved |

**总结**：-

