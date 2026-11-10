# 运行记录：case03_missing_info

- 模式：**mock**（ScriptedLLM (离线 Mock，回放预设动作)）
- 请求：`REQ-003`  运行序号：1
- 上限：最多 15 轮模型调用 / 40 次工具调用

> 离线 Mock：动作序列是预先写好的回放，只验证流程，不代表真实模型决策。

| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |
|---|---|---|---|---|---|---|
| 1 | 1 | `read_material` | {"material_id": "M03"} | 《新年倒计时模板》 bgm=owned，缺失字段: ['duration_sec', 'cover_url'] | 读取M03元数据 | `check_rules` |
| 2 | 2 | `check_rules` | {"material_id": "M03", "channel": "feed"} | verdict=needs_info，命中: R01(needs_info) | 字段缺失，确认审核结论 | `submit_report` |
| 3 | 3 | `submit_report` | {"items": 1} | 提交最终结果 | 全部素材已有结论 | `（结束）` |

## 最终结果

- task_status: **needs_user_action**  模型已提交结果
- published: False

| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |
|---|---|---|---|---|---|---|---|
| M03 | needs_info | 缺少必填字段: duration_sec, cover_url，需运营补充 | 12:00 | - | - | 未保存: not_attempted  | needs_info |

**总结**：M03信息缺失，未保存草稿。

