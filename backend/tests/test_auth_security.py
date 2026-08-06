"""A3/A4 安全加固的测试：注册 Schema 校验 + 验证码存储/爆破防护。

验证码部分使用本地 Redis db 15（与限流测试同库，用例前后 FLUSHDB），
Redis 未启动时跳过；Schema 部分无外部依赖，总是运行。
"""
import pytest
import redis
from fastapi import HTTPException
from pydantic import ValidationError

from schemas.auth import RegisterRequest, SendCodeRequest
from services import auth_service

TEST_REDIS_URL = "redis://localhost:6379/15"


# ---------- A4: 注册 Schema ----------


def _register_kwargs(**overrides):
    base = {"username": "user@example.com", "password": "goodpass123", "code": "123456"}
    base.update(overrides)
    return base


def test_valid_register_request():
    req = RegisterRequest(**_register_kwargs())
    assert req.username == "user@example.com"


@pytest.mark.parametrize("bad_password", ["", "short7c", "1234567"])
def test_password_too_short_rejected(bad_password):
    with pytest.raises(ValidationError):
        RegisterRequest(**_register_kwargs(password=bad_password))


def test_password_over_72_bytes_rejected():
    with pytest.raises(ValidationError):
        RegisterRequest(**_register_kwargs(password="a" * 73))
    # 24 个中文字符 = 72 字节，放行；25 个 = 75 字节，拒绝
    RegisterRequest(**_register_kwargs(password="密" * 24))
    with pytest.raises(ValidationError):
        RegisterRequest(**_register_kwargs(password="密" * 25))


@pytest.mark.parametrize("bad_email", ["notanemail", "a@b", "user@", "@example.com", "user @example.com"])
def test_bad_email_rejected(bad_email):
    with pytest.raises(ValidationError):
        RegisterRequest(**_register_kwargs(username=bad_email))
    with pytest.raises(ValidationError):
        SendCodeRequest(username=bad_email)


@pytest.mark.parametrize("bad_code", ["", "12345", "1234567", "abcdef", "12 456"])
def test_bad_code_format_rejected(bad_code):
    with pytest.raises(ValidationError):
        RegisterRequest(**_register_kwargs(code=bad_code))


# ---------- A3: 验证码存储与爆破防护 ----------


@pytest.fixture
def code_redis(monkeypatch):
    client = redis.Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    try:
        client.ping()
    except Exception:
        pytest.skip("本地 Redis 未启动，跳过验证码测试")
    client.flushdb()
    monkeypatch.setattr(auth_service, "_redis", client)
    yield client
    client.flushdb()
    client.close()


EMAIL = "t@example.com"


def test_code_is_six_digits_and_stored_with_ttl(code_redis):
    code = auth_service.store_code(EMAIL)
    assert len(code) == 6 and code.isdigit()
    ttl = code_redis.ttl(f"authcode:{EMAIL}")
    assert 0 < ttl <= auth_service.CODE_TTL_SECONDS


def test_correct_code_consumed_once(code_redis):
    code = auth_service.store_code(EMAIL)
    auth_service.verify_and_consume_code(EMAIL, code)
    # 第二次使用同一验证码：已被消费
    with pytest.raises(HTTPException) as exc:
        auth_service.verify_and_consume_code(EMAIL, code)
    assert exc.value.status_code == 400


def test_wrong_code_five_times_invalidates(code_redis):
    code = auth_service.store_code(EMAIL)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        with pytest.raises(HTTPException):
            auth_service.verify_and_consume_code(EMAIL, wrong)
    # 第 6 次：即使拿着正确验证码也已失效
    with pytest.raises(HTTPException) as exc:
        auth_service.verify_and_consume_code(EMAIL, code)
    assert "失效" in exc.value.detail or "获取" in exc.value.detail
    assert code_redis.exists(f"authcode:{EMAIL}") == 0


def test_few_failures_then_success_ok(code_redis):
    code = auth_service.store_code(EMAIL)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(4):
        with pytest.raises(HTTPException):
            auth_service.verify_and_consume_code(EMAIL, wrong)
    auth_service.verify_and_consume_code(EMAIL, code)  # 第 5 次给对的，应放行


def test_resend_resets_attempts(code_redis):
    auth_service.store_code(EMAIL)
    wrong = "999999"
    for _ in range(4):
        with pytest.raises(HTTPException):
            auth_service.verify_and_consume_code(EMAIL, wrong)
    new_code = auth_service.store_code(EMAIL)  # 重新发送：覆盖旧码并清零计数
    assert code_redis.hget(f"authcode:{EMAIL}", "attempts") == "0"
    auth_service.verify_and_consume_code(EMAIL, new_code)
