"""把 examples/cases 下的全部验收用例用离线 Mock 跑一遍，并执行与真实模型相同的自动核对。"""
import pytest

from schedule_agent.cases import load_cases, mock_factory, run_case

CASES = load_cases()


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_case_mock(case, tmp_path):
    r = run_case(case, mock_factory, "mock", tmp_path / "out", tmp_path / "state")
    failed = [f"{c['name']}: {c['detail']}" for c in r["checks"] if not c["passed"]]
    assert not failed, failed


def test_all_acceptance_points_covered():
    covers = {c for case in CASES for c in case["covers"]}
    for point in ["正常排期", "素材信息缺失", "规则风险", "时段冲突", "重复提交", "保存失败"]:
        assert point in covers, f"缺少验收点用例：{point}"
