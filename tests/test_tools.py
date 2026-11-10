"""工具层的硬约束：不依赖模型，直接验证。"""
from conftest import CH, DATE, item


def save(tb, mid, t, conf=False, items=None):
    return tb.call("save_draft", {"material_id": mid, "channel": CH, "date": DATE, "time": t,
                                  "needs_confirmation": conf, "confirmation_items": items or [], "reason": "t"})


def test_rule_verdicts(make_toolbox):
    tb = make_toolbox([item("M01", "18:00")])
    v = {m: tb.call("check_rules", {"material_id": m, "channel": CH})["verdict"]
         for m in ["M01", "M02", "M03", "M04", "M05", "M06"]}
    assert v == {"M01": "pass", "M02": "pass", "M03": "needs_info", "M04": "needs_verification",
                 "M05": "needs_verification", "M06": "block"}


def test_license_lookup_changes_verdict(make_toolbox):
    tb = make_toolbox([item("M04", "19:00"), item("M05", "19:00")])
    assert tb.call("lookup_license", {"material_id": "M04"})["license_status"] == "expired"
    assert tb.call("lookup_license", {"material_id": "M05"})["license_status"] == "valid"
    assert tb.call("check_rules", {"material_id": "M04", "channel": CH})["verdict"] == "block"
    assert tb.call("check_rules", {"material_id": "M05", "channel": CH})["verdict"] == "pass"


def test_missing_material(make_toolbox):
    tb = make_toolbox([item("M99", "18:00")])
    r = tb.call("read_material", {"material_id": "M99"})
    assert r["ok"] is False and r["error_code"] == "NOT_FOUND"


def test_query_slots_reflects_schedule(make_toolbox):
    tb = make_toolbox([item("M01", "18:00")])
    r = tb.call("query_slots", {"channel": CH, "date": DATE})
    assert r["free_times"] == ["10:00", "12:00", "19:00", "20:00"]


def test_save_rejects_occupied_slot(make_toolbox, store):
    tb = make_toolbox([item("M01", "18:00")])
    r = save(tb, "M01", "18:00")
    assert r["ok"] is False and r["error_code"] == "SLOT_CONFLICT"
    assert store.all() == []


def test_save_changed_time_requires_confirmation(make_toolbox, store):
    tb = make_toolbox([item("M01", "18:00")])
    r = save(tb, "M01", "19:00", conf=False)
    assert r["error_code"] == "CONFIRMATION_REQUIRED"
    r = save(tb, "M01", "19:00", conf=True, items=["改到19:00需确认"])
    assert r["ok"] and r["draft"]["status"] == "pending_confirmation" and r["draft"]["published"] is False


def test_fixed_time_cannot_be_changed(make_toolbox, store):
    tb = make_toolbox([item("M02", "18:00", "fixed")])
    r = save(tb, "M02", "19:00", conf=True)
    assert r["error_code"] == "HARD_CONSTRAINT_VIOLATION"
    assert store.all() == []


def test_date_cannot_be_changed(make_toolbox):
    tb = make_toolbox([item("M02", "20:00")])
    r = tb.call("save_draft", {"material_id": "M02", "channel": CH, "date": "2026-11-13", "time": "20:00",
                               "needs_confirmation": True})
    assert r["error_code"] == "HARD_CONSTRAINT_VIOLATION"


def test_review_must_pass_before_save(make_toolbox, store):
    tb = make_toolbox([item("M03", "12:00"), item("M05", "19:00"), item("M06", "20:00")])
    assert save(tb, "M03", "12:00")["error_code"] == "REVIEW_NOT_PASSED"
    assert save(tb, "M05", "19:00")["error_code"] == "REVIEW_NOT_PASSED"  # 未补查
    assert save(tb, "M06", "20:00")["error_code"] == "REVIEW_NOT_PASSED"
    assert store.all() == []


def test_material_not_in_request(make_toolbox):
    tb = make_toolbox([item("M02", "20:00")])
    assert save(tb, "M01", "20:00")["error_code"] == "NOT_IN_REQUEST"


def test_duplicate_save_is_idempotent(make_toolbox, store):
    tb = make_toolbox([item("M02", "20:00")])
    a = save(tb, "M02", "20:00")
    b = save(tb, "M02", "20:00")
    assert a["action"] == "created" and b["action"] == "deduplicated"
    assert a["draft"]["draft_id"] == b["draft"]["draft_id"]
    assert len(store.all()) == 1


def test_duplicate_across_runs_ignores_wording(make_toolbox, store):
    tb1 = make_toolbox([item("M01", "18:00")])
    save(tb1, "M01", "19:00", conf=True, items=["措辞A"])
    tb2 = make_toolbox([item("M01", "18:00")])  # 新一轮运行，同一个存储
    r = save(tb2, "M01", "19:00", conf=True, items=["措辞完全不同的B"])
    assert r["action"] == "deduplicated" and len(store.all()) == 1


def test_resave_new_slot_updates_same_draft(make_toolbox, store):
    tb = make_toolbox([item("M01", "18:00")])
    save(tb, "M01", "19:00", conf=True)
    tb2 = make_toolbox([item("M01", "18:00")],
                       overrides={"add_occupied": [{"date": DATE, "channel": CH, "time": "19:00", "by": "M92"}]})
    assert save(tb2, "M01", "19:00", conf=True)["error_code"] == "SLOT_CONFLICT"
    r = save(tb2, "M01", "20:00", conf=True)
    assert r["action"] == "updated" and r["draft"]["version"] == 2
    drafts = store.all()
    assert len(drafts) == 1 and drafts[0]["time"] == "20:00"


def test_two_materials_cannot_share_slot(make_toolbox, store):
    tb = make_toolbox([item("M01", "18:00"), item("M02", "19:00")])
    assert save(tb, "M02", "19:00")["ok"]
    assert save(tb, "M01", "19:00", conf=True)["error_code"] == "SLOT_CONFLICT"
    slots = tb.call("query_slots", {"channel": CH, "date": DATE, "material_id": "M02"})
    assert "19:00" in slots["available_times"] and "19:00" not in slots["free_times"]


def test_save_failure_injection(make_toolbox, store):
    tb = make_toolbox([item("M02", "20:00")], faults={"save_draft": {"mode": "always"}})
    r = save(tb, "M02", "20:00")
    assert r["ok"] is False and r["error_code"] == "STORAGE_UNAVAILABLE" and r["retryable"]
    assert store.all() == []


def test_save_failure_only_after_validation(make_toolbox, store):
    """first_n 故障只在真正写库时消耗：校验失败的调用不会“吃掉”注入的故障。"""
    tb = make_toolbox([item("M02", "20:00")], faults={"save_draft": {"mode": "first_n", "n": 1}})
    assert save(tb, "M02", "18:00", conf=True)["error_code"] == "SLOT_CONFLICT"
    assert save(tb, "M02", "20:00")["error_code"] == "STORAGE_UNAVAILABLE"
    assert save(tb, "M02", "20:00")["ok"]


def test_transient_tool_failure(make_toolbox):
    tb = make_toolbox([item("M02", "20:00")], faults={"query_slots": {"mode": "first_n", "n": 1}})
    assert tb.call("query_slots", {"channel": CH, "date": DATE})["retryable"] is True
    assert tb.call("query_slots", {"channel": CH, "date": DATE})["ok"] is True


def test_unknown_tool_and_bad_args(make_toolbox):
    tb = make_toolbox([item("M02", "20:00")])
    assert tb.call("publish_now", {})["error_code"] == "UNKNOWN_TOOL"
    assert tb.call("read_material", {"wrong": 1})["error_code"] == "BAD_ARGUMENTS"


def test_user_confirm_keeps_draft_unpublished(make_toolbox, store):
    tb = make_toolbox([item("M01", "18:00")])
    did = save(tb, "M01", "19:00", conf=True)["draft"]["draft_id"]
    d = store.confirm(did)
    assert d["status"] == "confirmed" and d["published"] is False
