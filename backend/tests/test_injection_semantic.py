"""语义近似注入检测单测：不同语言/说法的注入都被识别。"""

from core import config
from core.injection_guard import scan_semantic_injection

_MOCK_REASONABLE_VECTOR = [0.0] * 1024  # 全 0，基线
_MOCK_INJECTION_VECTOR = [1.0, 0.0] + [0.0] * 1022  # 简化示意


def test_semantic_injection_shows_failing_variants(monkeypatch):
    """EMBEDDING 模占位下也能走通分支逻辑（真管 bge 要花网真的）。"""
    # 强制 embedding 阶段返回一个接近已知 probe 的向量
    monkeypatch.setattr(
        "core.injection_guard._get_injection_embeddings",
        lambda: [[1.0, 0.0] + [0.0] * 1022] * 12,
    )
    from services.rag import embedding as _emb
    monkeypatch.setattr(_emb, "get_embedding",
        lambda text: [0.95, 0.31] + [0.0] * 1022,  # 接近 probe[0] -> cosine≈0.95
    )
    # 文本需超过最短门槛，否则 C25 起新增的短路会先于向量比对生效
    r = scan_semantic_injection("某条超过八个字的注入文本")
    assert r["is_suspicious"] is True


# ---------- C25 回归：误杀防护 ----------
#
# 2026-10-03 实测：阈值 0.62 时“问点什么/这个怎么改/重写一遍”被判 block
# （相似度冲到 0.68，排在良性段中间）；真注入最低也有 0.749。
# 修复：阈值上抬 0.72 + 短于 MIN_CHARS 不走语义层。以下用合成向量钉住这两条防线。


def test_short_text_never_burns_embedding(monkeypatch):
    """短句直接跳过语义层——装不下注入载荷，也压不住 embedding 噪声。"""
    burn_marker = []
    from services.rag import embedding as _emb
    monkeypatch.setattr(_emb, "get_embedding", lambda text: burn_marker.append(text) or [0.0] * 1024)
    monkeypatch.setattr(
        "core.injection_guard._get_injection_embeddings",
        lambda: [_MOCK_INJECTION_VECTOR],
    )
    r = scan_semantic_injection("太短了")  # 4 字 < MIN_CHARS(8)
    assert r == {"is_suspicious": False, "similarity": 0.0, "skipped": "too_short"}
    assert burn_marker == []  # 一次 embedding 调用都没发生


def test_threshold_reads_config(monkeypatch):
    """阈值从 config 读，不传参时生效；And 调低后攻击能被语义层接住。"""
    # 合成向量与 probe 余弦 = 0.7：高于旧阈值 0.62（误杀区），低于新默认 0.72
    import math
    v = [0.7, math.sqrt(1 - 0.7**2)] + [0.0] * 1022
    monkeypatch.setattr(
        "core.injection_guard._get_injection_embeddings",
        lambda: [_MOCK_INJECTION_VECTOR],
    )
    from services.rag import embedding as _emb
    monkeypatch.setattr(_emb, "get_embedding", lambda text: v)

    r = scan_semantic_injection("这是一段处于灰色地带的良性文本")
    assert r["is_suspicious"] is False  # 新默认 0.72 放行 0.7

    monkeypatch.setattr(config, "INJECTION_SEMANTIC_THRESHOLD", 0.5)
    r2 = scan_semantic_injection("这是一段处于灰色地带的良性文本")
    assert r2["is_suspicious"] is True  # 调低阈值后同一向量被拦
