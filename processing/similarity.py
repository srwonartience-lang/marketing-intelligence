import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-zA-Z0-9가-힣]+")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "being", "at", "by", "from", "as",
    "that", "this", "it", "its", "how", "what", "why", "your", "you", "we",
    "will", "can", "has", "have", "had", "not", "into", "about", "after", "over",
}


def tokenize(text: str) -> list:
    if not text:
        return []
    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def build_tfidf_vectors(documents: dict) -> dict:
    """documents: {doc_id: text}. 외부 라이브러리 없이 순수 Python으로 TF-IDF
    벡터를 만든다. 비교 대상 문서가 많을수록(=코퍼스가 클수록) 흔한 단어(marketing,
    google 등)의 가중치가 자동으로 낮아지고, 특정 문서들에만 공통으로 등장하는
    단어의 가중치가 높아져 "같은 사건" 판별에 유리해진다."""
    term_freqs = {doc_id: Counter(tokenize(text)) for doc_id, text in documents.items()}
    doc_count = len(term_freqs)

    document_frequency = Counter()
    for tf in term_freqs.values():
        for term in tf:
            document_frequency[term] += 1

    vectors = {}
    for doc_id, tf in term_freqs.items():
        vector = {}
        for term, count in tf.items():
            idf = math.log((1 + doc_count) / (1 + document_frequency[term])) + 1
            vector[term] = count * idf
        vectors[doc_id] = vector
    return vectors


def cosine_similarity(vec_a: dict, vec_b: dict) -> float:
    if not vec_a or not vec_b:
        return 0.0
    common_terms = set(vec_a) & set(vec_b)
    dot_product = sum(vec_a[t] * vec_b[t] for t in common_terms)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)
