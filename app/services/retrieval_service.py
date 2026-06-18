import math
import re
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass
class ScoredItem:
    item: object
    score: float


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(left[i] * right[i] for i in range(size))
    left_norm = math.sqrt(sum(left[i] * left[i] for i in range(size))) or 1.0
    right_norm = math.sqrt(sum(right[i] * right[i] for i in range(size))) or 1.0
    return dot / (left_norm * right_norm)


def chunk_text(text: str, *, max_chars: int = 700, overlap: int = 80) -> list[str]:
    cleaned = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not cleaned:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + max_chars, len(cleaned))
        chunks.append(cleaned[start:end].strip())
        if end >= len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


DOMAIN_TERMS = [
    "租赁备案",
    "备案",
    "材料",
    "合同",
    "押金",
    "退租",
    "核验码",
    "房源核验",
    "实名",
    "经纪",
    "买卖",
    "交易",
    "网签",
    "产权",
    "抵押",
    "查封",
    "税费",
    "居住证",
    "落户",
]


def extract_terms(text: str) -> list[str]:
    terms = [term for term in DOMAIN_TERMS if term in text]
    terms.extend(re.findall(r"[A-Za-z0-9_]{2,}", text.lower()))
    return list(dict.fromkeys(terms))


def keyword_score(query: str, text: str) -> float:
    terms = extract_terms(query)
    if not terms:
        return 0.0
    score = 0.0
    for term in terms:
        if term in text:
            score += 1.0 if len(term) <= 2 else 2.0
    return score / max(len(terms), 1)


def top_keyword_matches(query: str, items: list[T], texts: list[str], top_k: int) -> list[tuple[T, float]]:
    scored = [(item, keyword_score(query, text)) for item, text in zip(items, texts, strict=False)]
    return [(item, score) for item, score in sorted(scored, key=lambda pair: pair[1], reverse=True)[:top_k] if score > 0]

