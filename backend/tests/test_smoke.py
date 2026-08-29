"""Smoke test：证明 backend/tests 可被 pytest 发现，且不触碰运行时业务库。"""


def test_pytest_discovers_backend_tests() -> None:
    assert True
