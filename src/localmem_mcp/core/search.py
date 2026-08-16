"""Pure helpers for hybrid (vector + keyword) search."""

from __future__ import annotations

import math
from collections.abc import Sequence

#: Weight given to the keyword (FTS5) signal when blending with cosine
#: similarity. Vector similarity carries the rest.
KEYWORD_WEIGHT = 0.25


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _fts_query(text: str) -> str:
    """Turn free text into a safe FTS5 OR-query.

    User text can contain FTS operators (``AND``, ``"``, ``*``, ``:``) that
    would either error or change the query's meaning, so each word is quoted
    and joined explicitly.
    """
    words = [w for w in "".join(c if c.isalnum() else " " for c in text).split() if w]
    return " OR ".join(f'"{w}"' for w in words)
