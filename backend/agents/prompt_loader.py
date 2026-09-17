"""System Prompt 文件化装配（C17）。

neyria.py 里几十条规则曾经是内联 f-string，改一处要动代码主文件。
现在拆为 prompts/*.md 按文件名顺序拼装：
- 加新规则 = 放一个 .md 进目录，或编辑现有文件，零代码改动；
- `"{profile_section}"` 占位符在装配时由运行时注入（仅此一项是变量）。

注意：不要用 str.format 拼装正文——规则文件里存在 `${upstream.result.content}`、
`{"query": ...}` 这类花括号，format 会把它们炸没。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=1)
def _sections() -> tuple[str, ...]:
    files = sorted(PROMPTS_DIR.glob("*.md"))
    if not files:
        raise RuntimeError(f"prompts 目录为空: {PROMPTS_DIR}")
    return tuple(f.read_text(encoding="utf-8").strip("\n") for f in files)


def build_base_prompt(profile: str) -> str:
    parts: list[str] = []
    for section in _sections():
        parts.append(section.replace("{profile_section}", profile))
    return "\n\n".join(parts) + "\n"


def reload_cache() -> None:
    """测试/热更用：清空缓存后下次装配重读文件。"""
    _sections.cache_clear()
