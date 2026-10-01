"""SiliconFlow 视频 Provider 单测：API 合约（根级 prompt/轮询状态机）、
转存与资产登记、未配置/失败/超时错误路径（E2 视频链路）。"""

from pathlib import Path

import pytest

from schemas.capability import VideoGenerateInput
from services.capabilities import siliconflow_video
from services.capabilities.zhipu_text import ModelNotConfiguredError


def _inputs(**kw):
    data = {"prompt": "雨夜城市街道", "style": "电影写实", "ratio": "16:9", "duration": "5 秒"}
    data.update(kw)
    return VideoGenerateInput(**data)


def test_unconfigured_raises_model_unavailable(monkeypatch):
    monkeypatch.setattr(siliconflow_video.config, "SILICONFLOW_API_KEY", "")
    with pytest.raises(ModelNotConfiguredError):
        siliconflow_video.generate_video(_inputs())


class _Post:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_submit_sends_root_level_prompt_and_params(monkeypatch):
    """API 合约（真机验证 2026-09-30）：prompt/image_size/duration 都在根级，不嵌套。"""
    captured = {}

    def fake_post(url, **kw):
        captured["url"] = url
        captured["json"] = kw["json"]
        return _Post({"requestId": "req-123"})

    monkeypatch.setattr(siliconflow_video.config, "SILICONFLOW_API_KEY", "sk-test")
    monkeypatch.setattr(siliconflow_video.httpx, "post", fake_post)
    request_id = siliconflow_video._submit("镜头推进。风格：电影写实。", "1280x720", 5)

    assert request_id == "req-123"
    assert captured["url"].endswith("/v1/video/submit")
    body = captured["json"]
    assert body["prompt"] == "镜头推进。风格：电影写实。"
    assert body["image_size"] == "1280x720"
    assert body["duration"] == 5
    assert "input" not in body  # 嵌套写法会被上游拒（20016）


def test_wait_polls_until_succeed(monkeypatch):
    """轮询状态机：InQueue → InProgress → Succeed，取 videos[0].url。"""
    states = iter(["InQueue", "InProgress", "Succeed"])
    calls = {"n": 0}

    def fake_post(url, **kw):
        calls["n"] += 1
        status = next(states)
        payload = {"status": status, "results": None}
        if status == "Succeed":
            payload["results"] = {"videos": [{"url": "https://s3.example/v.mp4?sig=x"}]}
        return _Post(payload)

    monkeypatch.setattr(siliconflow_video.httpx, "post", fake_post)
    monkeypatch.setattr(siliconflow_video.time, "sleep", lambda _s: None)
    url = siliconflow_video._wait_for_video("req-123")

    assert url == "https://s3.example/v.mp4?sig=x"
    assert calls["n"] == 3


def test_wait_failed_status_raises_with_reason(monkeypatch):
    def fake_post(url, **kw):
        return _Post({"status": "Failed", "reason": "内容审核未通过"})

    monkeypatch.setattr(siliconflow_video.httpx, "post", fake_post)
    monkeypatch.setattr(siliconflow_video.time, "sleep", lambda _s: None)
    with pytest.raises(RuntimeError, match="内容审核未通过"):
        siliconflow_video._wait_for_video("req-bad")


def test_wait_timeout_raises(monkeypatch):
    def fake_post(url, **kw):
        return _Post({"status": "InProgress", "results": None})

    monkeypatch.setattr(siliconflow_video.httpx, "post", fake_post)
    # 把轮询总预算归零：循环条件第一轮即不成立，立刻判超时退出。
    # ⚠️ 别 mock monotonic 为恒定值——那会让 deadline=600 而条件永真，死循环（踩过的坑）
    monkeypatch.setattr(siliconflow_video, "_POLL_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(siliconflow_video.time, "sleep", lambda _s: None)
    with pytest.raises(RuntimeError, match="超时"):
        siliconflow_video._wait_for_video("req-slow")


def test_generate_video_downloads_and_rehosts(monkeypatch, tmp_path):
    """成功路径：S3 临时 URL 立即下载转存本地，返回我方持久路径 + 资产登记结构。"""
    monkeypatch.setattr(siliconflow_video.config, "SILICONFLOW_API_KEY", "sk-test")
    monkeypatch.setattr(siliconflow_video.config, "DOCUMENT_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(
        siliconflow_video,
        "_submit",
        lambda *a: "req-ok",
    )

    def fake_status_post(url, **kw):
        return _Post(
            {"status": "Succeed", "results": {"videos": [{"url": "https://s3.example/v.mp4"}]}}
        )

    class _Get:
        status_code = 200
        content = b"\x00\x00\x00\x18ftypmp4fake-bytes"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        siliconflow_video.httpx, "post", fake_status_post, raising=True
    )
    monkeypatch.setattr(siliconflow_video.time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        siliconflow_video.httpx, "get", lambda url, **kw: _Get()
    )

    out = siliconflow_video.generate_video(_inputs())
    assert out["asset_path"].startswith("/api/assets/")
    assert out["asset_path"].endswith(".mp4")
    assert out["asset"]["capability_id"] == "video.generate"
    assert out["content"] == f"![视频]({out['asset_path']})"
    # 文件真的转存到了本地 assets 目录
    filename = out["asset_path"].split("/")[-1]
    assert Path(tmp_path.parent / "assets" / filename).is_file()
    assert out["usage"]["model"] == siliconflow_video.config.VIDEO_MODEL
