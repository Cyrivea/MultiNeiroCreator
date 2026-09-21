"""语义近似注入检测单测：不同语言/说法的注入都被识别。"""

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
    r = scan_semantic_injection("某条注入")
    assert r["is_suspicious"] is True
