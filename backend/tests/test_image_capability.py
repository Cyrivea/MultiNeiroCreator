"""SiliconFlow 图像 Provider 单测：从调约定、生成后果转存、错误路径（E2）。"""

from pathlib import Path

import pytest

from schemas.capability import ImageGenerateInput
from services.capabilities import siliconflow_image
from services.capabilities.zhipu_text import ModelNotConfiguredError


def _inputs(**kw):
    kw.setdefault("__styles", "电影概念艺术")
    data = {"prompt": "海边黄昏", "style": "电影概念艺术", "ratio": "1:1", "palette": "深蓝与紫色"}
    data.update(kw)
    return ImageGenerateInput(**data)


def test_unconfigured_raises_model_unavailable(monkeypatch):
    monkeypatch.setattr(siliconflow_image.config, "SILICONFLOW_API_KEY", "")
    with pytest.raises(ModelNotConfiguredError):
        siliconflow_image.generate_image(_inputs())


def test_success_downloads_and_rehosts_asset(monkeypatch, tmp_path):
    monkeypatch.setattr(siliconflow_image.config, "SILICONFLOW_API_KEY", "sk-test")
    monkeypatch.setattr(siliconflow_image.config, "DOCUMENT_STORAGE_DIR", tmp_path)

    class _Post:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"images": [{"url": "https://s3.example/temp.png?sig=x"}]}

    get_calls = []

    class _Get:
        status_code = 200
        content = b"\x89PNG fake-bytes"

        def raise_for_status(self):
            return None

    def fake_post(url, **kw):
        assert url.endswith("/images/generations")
        assert kw["json"]["image_size"] == "1024x1024"
        return _Post()

    def fake_get(url, **kw):
        get_calls.append(url)
        assert "*不能带签名后过期*" not in url or "sig=x" in url  # 原样下载
        return _Get()

    monkeypatch.setattr(siliconflow_image.httpx, "post", fake_post)
    monkeypatch.setattr(siliconflow_image.httpx, "get", fake_get)

    out = siliconflow_image.generate_image(_inputs())
    assert out["usage"]["model"] == "Kwai-Kolors/Kolors"
    asset_url = out["asset_path"]
    assert asset_url.startswith("/api/assets/")
    filename = asset_url.split("/")[-1]
    assert Path(tmp_path.parent / "assets" / filename).is_file()


def test_provider_4xx_becomes_runtime_error(monkeypatch, tmp_path):
    import httpx as real_httpx

    monkeypatch.setattr(siliconflow_image.config, "SILICONFLOW_API_KEY", "sk-test")

    class _Forbidden:
        def raise_for_status(self):
            request = real_httpx.Request("POST", "https://api.siliconflow.cn/v1/images/generations")
            raise real_httpx.HTTPStatusError(
                "nope", request=request, response=real_httpx.Response(403, request=request)
            )

    monkeypatch.setattr(siliconflow_image.httpx, "post", lambda url, **kw: _Forbidden())
    with pytest.raises(RuntimeError) as exc:
        siliconflow_image.generate_image(_inputs())
    assert "403" in str(exc.value)
