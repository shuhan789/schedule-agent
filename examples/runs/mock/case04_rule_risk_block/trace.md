# 运行记录：case04_rule_risk_block

- 模式：**mock**（ScriptedLLM (离线 Mock，回放预设动作)）
- 请求：`REQ-004`  运行序号：1
- 上限：最多 15 轮模型调用 / 40 次工具调用

> 离线 Mock：动作序列是预先写好的回放，只验证流程，不代表真实模型决策。

| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |
|---|---|---|---|---|---|---|
| 1 | 1 | `read_material` | {"material_id": "M04"} | 《复古胶片滤镜合集》 bgm=unknown，字段完整 | 读取M04元数据 | `read_material` |
| 2 | 1 | `read_material` | {"material_id": "M06"} | 《全网第一的卡点模板》 bgm=owned，字段完整 | 读取M06元数据 | `check_rules` |
| 3 | 2 | `check_rules` | {"material_id": "M04", "channel": "feed"} | verdict=needs_verification，命中: R03(needs_verification) | 审核M04 | `check_rules` |
| 4 | 2 | `check_rules` | {"material_id": "M06", "channel": "feed"} | verdict=block，命中: R02(block) | 审核M06 | `lookup_license` |
| 5 | 3 | `lookup_license` | {"material_id": "M04"} | TRK-204 授权状态=expired | M04背景音乐授权未知，补查版权库 | `check_rules` |
| 6 | 4 | `check_rules` | {"material_id": "M04", "channel": "feed"} | verdict=block，命中: R03(block) | 补查完成，重新审核 | `submit_report` |
| 7 | 5 | `submit_report` | {"items": 2} | 提交最终结果 | 全部素材已有结论 | `（结束）` |

## 最终结果

- task_status: **needs_user_action**  模型已提交结果
- published: False

| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |
|---|---|---|---|---|---|---|---|
| M04 | blocked | 背景音乐 TRK-204 补查结果为 expired，无有效授权 | 19:00 | - | - | 未保存: not_attempted  | blocked |
| M06 | blocked | 标题/描述含广告法极限词: 全网第一，需修改文案 | 20:00 | - | - | 未保存: not_attempted  | blocked |

**总结**：M04、M06均被阻断，未保存草稿。

