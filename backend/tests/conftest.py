"""tests 全局夹具：在任何被测模块 import 之前准备测试环境变量。

conftest 由 pytest 在收集阶段最先加载，早于测试模块的顶层 import，
所以这里 setdefault 的值能被 core/config.py 读到。
"""

import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")


@pytest.fixture(autouse=True)
def _billing_mode_off(monkeypatch):
    """测试默认关闭计费门控：老的用例不应被“积分不足”拒绝；
    计费测试自己显式 monkeypatch 成 track/enforce。"""
    monkeypatch.setattr("core.config.BILLING_MODE", "off")
