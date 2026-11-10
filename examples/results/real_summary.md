# 用例运行汇总（real）

- 模型：deepseek-chat @ https://api.deepseek.com
- 通过：**12/12**

| 用例 | 覆盖验收点 | 任务状态 | 各素材最终状态 | 工具调用 | Guard更正 | 结果 | Trace |
|---|---|---|---|---|---|---|---|
| case01_normal | 正常排期 | completed | M02:draft_saved | 4 | 0 | ✅ | `examples/runs/real/case01_normal/` |
| case02_slot_conflict | 时段冲突、确认边界 | needs_user_action | M01:draft_saved_pending_confirmation | 4 | 0 | ✅ | `examples/runs/real/case02_slot_conflict/` |
| case03_missing_info | 素材信息缺失、资料不足 | needs_user_action | M03:needs_info | 3 | 0 | ✅ | `examples/runs/real/case03_missing_info/` |
| case04_rule_risk_block | 规则风险、补查、阻断 | needs_user_action | M04:blocked, M06:blocked | 7 | 0 | ✅ | `examples/runs/real/case04_rule_risk_block/` |
| case05_risk_verified_pass | 规则风险、补查、正常排期 | completed | M05:draft_saved | 6 | 0 | ✅ | `examples/runs/real/case05_risk_verified_pass/` |
| case06_duplicate_submit | 重复提交、防重复 | needs_user_action | M01:draft_saved_pending_confirmation | 8 | 0 | ✅ | `examples/runs/real/case06_duplicate_submit/` |
| case07_resubmit_after_slot_change | 时段冲突、重复提交、审核要点：更换占用时段 | needs_user_action | M01:draft_saved_pending_confirmation | 8 | 0 | ✅ | `examples/runs/real/case07_resubmit_after_slot_change/` |
| case08_save_failure | 保存失败、工具失败 | partial_failed | M02:save_failed | 5 | 0 | ✅ | `examples/runs/real/case08_save_failure/` |
| case09_tool_transient_failure | 工具失败、正常排期 | completed | M02:draft_saved | 5 | 0 | ✅ | `examples/runs/real/case09_tool_transient_failure/` |
| case10_fixed_time_conflict | 时段冲突、确认边界、硬性要求 | needs_user_action | M02:awaiting_confirmation | 3 | 0 | ✅ | `examples/runs/real/case10_fixed_time_conflict/` |
| case11_step_limit | 步数上限 | incomplete | M01:unresolved, M02:unresolved | 6 | 0 | ✅ | `examples/runs/real/case11_step_limit/` |
| case12_batch | 正常排期、时段冲突、规则风险、无冲突排期 | needs_user_action | M01:draft_saved_pending_confirmation, M05:draft_saved, M02:draft_saved, M06:blocked | 14 | 0 | ✅ | `examples/runs/real/case12_batch/` |

## 逐项核对

### case01_normal — 正常排期：无风险、要求时段空闲

- ✅ 从未发布 — published 字段恒为 False
- ✅ 草稿无时段冲突 — 无冲突
- ✅ 保存状态与存储一致 — 一致
- ✅ task_status ∈ ['completed'] — 实际 completed（模型已提交结果）
- ✅ M02 最终状态 ∈ ['draft_saved'] — 实际 draft_saved
- ✅ M02 建议时段 ∈ ['20:00'] — 实际 20:00
- ✅ M02 待确认 = False — 实际 False；[]
- ✅ M02 草稿已保存 = True — {"saved": true, "action": "created", "draft_id": "DRAFT-FB7A1E15", "time": "20:00", "status": "ready", "version": 1}
- ✅ 存储中 M02 草稿数 = 1 — 实际 1：[('DRAFT-FB7A1E15', '20:00', 'v1')]

### case02_slot_conflict — 参考实例：M01要求18:00但已占用，建议19:00并待确认

- ✅ 从未发布 — published 字段恒为 False
- ✅ 草稿无时段冲突 — 无冲突
- ✅ 保存状态与存储一致 — 一致
- ✅ task_status ∈ ['needs_user_action'] — 实际 needs_user_action（模型已提交结果）
- ✅ M01 最终状态 ∈ ['draft_saved_pending_confirmation'] — 实际 draft_saved_pending_confirmation
- ✅ M01 审核结论 = approved — 实际 approved；风险: []
- ✅ M01 建议时段 ∉ ['18:00', '21:00', None] — 实际 19:00
- ✅ M01 待确认 = True — 实际 True；['原定 18:00 已被占用（M90），建议改为 19:00，需用户确认']
- ✅ M01 草稿已保存 = True — {"saved": true, "action": "created", "draft_id": "DRAFT-CF6562FB", "time": "19:00", "status": "pending_confirmation", "version": 1}
- ✅ 存储中 M01 草稿数 = 1 — 实际 1：[('DRAFT-CF6562FB', '19:00', 'v1')]
- ✅ 存储中 M01 时段 ∉ ['18:00'] — 实际 ['19:00']

### case03_missing_info — 素材信息缺失：M03缺封面与时长

- ✅ 从未发布 — published 字段恒为 False
- ✅ 草稿无时段冲突 — 无冲突
- ✅ 保存状态与存储一致 — 一致
- ✅ task_status ∈ ['needs_user_action'] — 实际 needs_user_action（模型已提交结果）
- ✅ M03 最终状态 ∈ ['needs_info'] — 实际 needs_info
- ✅ M03 草稿已保存 = False — {"saved": false, "action": "not_attempted"}
- ✅ M03 风险原因提及 ['duration_sec', 'cover_url'] — 缺少必填字段: duration_sec, cover_url，需运营补充
- ✅ 存储中 M03 草稿数 = 0 — 实际 0：[]

### case04_rule_risk_block — 规则风险：M04补查后授权过期→阻断；M06含极限词→阻断

- ✅ 从未发布 — published 字段恒为 False
- ✅ 草稿无时段冲突 — 无冲突
- ✅ 保存状态与存储一致 — 一致
- ✅ task_status ∈ ['needs_user_action'] — 实际 needs_user_action（模型已提交结果）
- ✅ M04 最终状态 ∈ ['blocked'] — 实际 blocked
- ✅ M04 审核结论 = blocked — 实际 blocked；风险: ['背景音乐 TRK-204 补查结果为 expired，无有效授权']
- ✅ M04 草稿已保存 = False — {"saved": false, "action": "not_attempted"}
- ✅ M04 风险原因提及 ['expired'] — 背景音乐 TRK-204 补查结果为 expired，无有效授权
- ✅ M06 最终状态 ∈ ['blocked'] — 实际 blocked
- ✅ M06 审核结论 = blocked — 实际 blocked；风险: ['标题/描述含广告法极限词: 全网第一，需修改文案']
- ✅ M06 草稿已保存 = False — {"saved": false, "action": "not_attempted"}
- ✅ M06 风险原因提及 ['全网第一'] — 标题/描述含广告法极限词: 全网第一，需修改文案
- ✅ 存储中 M04 草稿数 = 0 — 实际 0：[]
- ✅ 存储中 M06 草稿数 = 0 — 实际 0：[]
- ✅ 第1次运行调用 lookup_license {'material_id': 'M04'} ≥ 1 次 — 实际 1 次

### case05_risk_verified_pass — 规则风险补查后通过：M05授权有效→正常排期

- ✅ 从未发布 — published 字段恒为 False
- ✅ 草稿无时段冲突 — 无冲突
- ✅ 保存状态与存储一致 — 一致
- ✅ task_status ∈ ['completed'] — 实际 completed（模型已提交结果）
- ✅ M05 最终状态 ∈ ['draft_saved'] — 实际 draft_saved
- ✅ M05 建议时段 ∈ ['19:00'] — 实际 19:00
- ✅ M05 草稿已保存 = True — {"saved": true, "action": "created", "draft_id": "DRAFT-FB4F42DE", "time": "19:00", "status": "ready", "version": 1}
- ✅ 存储中 M05 草稿数 = 1 — 实际 1：[('DRAFT-FB4F42DE', '19:00', 'v1')]
- ✅ 第1次运行调用 lookup_license {'material_id': 'M05'} ≥ 1 次 — 实际 1 次

### case06_duplicate_submit — 重复提交：同一请求运行两次只产生一份草稿

- ✅ 从未发布 — published 字段恒为 False
- ✅ 草稿无时段冲突 — 无冲突
- ✅ 保存状态与存储一致 — 一致
- ✅ M01 待确认 = True — 实际 True；['原定 18:00 已被占用（M90），建议改为 19:00，需用户确认']
- ✅ M01 草稿已保存 = True — {"saved": true, "action": "deduplicated", "draft_id": "DRAFT-CF6562FB", "time": "19:00", "status": "pending_confirmation", "version": 1}
- ✅ M01 草稿动作 ∈ ['deduplicated'] — 实际 deduplicated
- ✅ 存储中 M01 草稿数 = 1 — 实际 1：[('DRAFT-CF6562FB', '19:00', 'v1')]
- ✅ 存储中 M01 时段 ∉ ['18:00'] — 实际 ['19:00']

### case07_resubmit_after_slot_change — 更换占用时段并重复提交：19:00被他人占用后重跑，原草稿改到新时段

- ✅ 从未发布 — published 字段恒为 False
- ✅ 草稿无时段冲突 — 无冲突
- ✅ 保存状态与存储一致 — 一致
- ✅ M01 最终状态 ∈ ['draft_saved_pending_confirmation'] — 实际 draft_saved_pending_confirmation
- ✅ M01 建议时段 ∉ ['18:00', '19:00', '21:00', None] — 实际 20:00
- ✅ M01 待确认 = True — 实际 True；['原定 18:00 已被占用（M90），建议改为 20:00，需用户确认']
- ✅ M01 草稿动作 ∈ ['updated'] — 实际 updated
- ✅ 存储中 M01 草稿数 = 1 — 实际 1：[('DRAFT-CF6562FB', '20:00', 'v2')]
- ✅ 存储中 M01 时段 ∉ ['18:00', '19:00'] — 实际 ['20:00']

### case08_save_failure — 保存失败：存储持续不可用，必须明确返回失败

- ✅ 从未发布 — published 字段恒为 False
- ✅ 草稿无时段冲突 — 无冲突
- ✅ 保存状态与存储一致 — 一致
- ✅ task_status ∈ ['partial_failed'] — 实际 partial_failed（模型已提交结果）
- ✅ M02 最终状态 ∈ ['save_failed'] — 实际 save_failed
- ✅ M02 草稿已保存 = False — {"saved": false, "action": "failed", "error_code": "STORAGE_UNAVAILABLE", "error": "草稿存储服务不可用，本次未保存"}
- ✅ 存储中 M02 草稿数 = 0 — 实际 0：[]

### case09_tool_transient_failure — 工具失败后恢复：时段查询首次超时，重试成功

- ✅ 从未发布 — published 字段恒为 False
- ✅ 草稿无时段冲突 — 无冲突
- ✅ 保存状态与存储一致 — 一致
- ✅ task_status ∈ ['completed'] — 实际 completed（模型已提交结果）
- ✅ M02 最终状态 ∈ ['draft_saved'] — 实际 draft_saved
- ✅ M02 草稿已保存 = True — {"saved": true, "action": "created", "draft_id": "DRAFT-FB7A1E15", "time": "20:00", "status": "ready", "version": 1}
- ✅ 第1次运行调用 query_slots {} ≥ 2 次 — 实际 2 次

### case10_fixed_time_conflict — 硬性要求：M02固定18:00但已占用，不得擅自改期

- ✅ 从未发布 — published 字段恒为 False
- ✅ 草稿无时段冲突 — 无冲突
- ✅ 保存状态与存储一致 — 一致
- ✅ task_status ∈ ['needs_user_action'] — 实际 needs_user_action（模型已提交结果）
- ✅ M02 最终状态 ∈ ['awaiting_confirmation'] — 实际 awaiting_confirmation
- ✅ M02 待确认 = True — 实际 True；['原定 2026-11-12 18:00（feed）已被素材 M90 占用；因该素材时间要求为 fixed，未擅自改期，请确认是否改用同日空闲时段 19:00（备选 20:00 / 12:00 / 10:00）']
- ✅ M02 草稿已保存 = False — {"saved": false, "action": "not_attempted"}
- ✅ 存储中 M02 草稿数 = 0 — 实际 0：[]

### case11_step_limit — 执行上限：最多3轮模型调用，未完成时明确返回 incomplete

- ✅ 从未发布 — published 字段恒为 False
- ✅ 草稿无时段冲突 — 无冲突
- ✅ 保存状态与存储一致 — 一致
- ✅ task_status ∈ ['incomplete'] — 实际 incomplete（未完成：模型调用轮数达到上限 3）
- ✅ 状态原因包含“上限” — 未完成：模型调用轮数达到上限 3
- ✅ M01 草稿已保存 = False — {"saved": false, "action": "not_attempted"}
- ✅ M02 草稿已保存 = False — {"saved": false, "action": "not_attempted"}

### case12_batch — 批量排期：4个素材，含冲突、补查、阻断，排期互不冲突

- ✅ 从未发布 — published 字段恒为 False
- ✅ 草稿无时段冲突 — 无冲突
- ✅ 保存状态与存储一致 — 一致
- ✅ task_status ∈ ['needs_user_action'] — 实际 needs_user_action（模型已提交结果）
- ✅ M01 最终状态 ∈ ['draft_saved_pending_confirmation'] — 实际 draft_saved_pending_confirmation
- ✅ M01 建议时段 ∉ ['18:00', '21:00', None] — 实际 12:00
- ✅ M01 待确认 = True — 实际 True；['原定 18:00 已被占用（M90），建议改为 12:00，需用户确认', '19:00 已分配给 M05、20:00 已分配给 M02，故未选更接近的时段']
- ✅ M05 最终状态 ∈ ['draft_saved', 'draft_saved_pending_confirmation'] — 实际 draft_saved
- ✅ M05 草稿已保存 = True — {"saved": true, "action": "created", "draft_id": "DRAFT-FB4F42DE", "time": "19:00", "status": "ready", "version": 1}
- ✅ M02 最终状态 ∈ ['draft_saved'] — 实际 draft_saved
- ✅ M02 建议时段 ∈ ['20:00'] — 实际 20:00
- ✅ M06 最终状态 ∈ ['blocked'] — 实际 blocked
- ✅ M06 草稿已保存 = False — {"saved": false, "action": "not_attempted"}
- ✅ 第1次运行调用 lookup_license {'material_id': 'M05'} ≥ 1 次 — 实际 1 次
