# 运行记录：case03_missing_info

- 模式：**real**（deepseek-chat @ https://api.deepseek.com）
- 请求：`REQ-003`  运行序号：1
- 上限：最多 15 轮模型调用 / 40 次工具调用

| # | 轮 | 动作 | 参数 | 返回摘要 | 决策依据(reason) | 后续动作 |
|---|---|---|---|---|---|---|
| 1 | 1 | `read_material` | {"material_id": "M03"} | 《新年倒计时模板》 bgm=owned，缺失字段: ['duration_sec', 'cover_url'] | 读取 M03 素材元数据，确认字段完整性与基本信息 | `check_rules` |
| 2 | 1 | `check_rules` | {"material_id": "M03", "channel": "feed"} | verdict=needs_info，命中: R01(needs_info) | 按 feed 渠道审核规则检查 M03 是否可排期 | `query_slots` |
| 3 | 2 | `query_slots` | {"channel": "feed", "date": "2026-11-12", "material_id": "M03"} | 空闲: ['10:00', '12:00', '19:00', '20:00']；占用: ['18:00(occupied:M90)', '21:00(occupied:M91)'] | 查询 2026-11-12 feed 渠道时段占用，为补齐信息后的排期提供参考 | `submit_report` |
| 4 | 3 | `submit_report` | {"items": 1} | 提交最终结果 | M03 审核为 needs_info 且未保存草稿，需向用户报告缺失字段与可用时段 | `（结束）` |

## 最终结果

- task_status: **needs_user_action**  模型已提交结果
- published: False

| 素材 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认 | 草稿 | 最终状态 |
|---|---|---|---|---|---|---|---|
| M03 | needs_info | 缺少必填字段: duration_sec, cover_url，需运营补充 | 12:00 | 12:00 | - | 未保存: not_attempted  | needs_info |

**总结**：M03（新年倒计时模板）审核结论为 needs_info：缺少 duration_sec 与 cover_url 两个必填字段，按规则未保存排期草稿。已确认 2026-11-12 feed 渠道 12:00 时段空闲，待运营补齐字段并通过审核后即可按原定时间排期。

