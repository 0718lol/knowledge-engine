"""Pure-Python TF-IDF text search over concepts."""
import math
import re
from collections import Counter
from database import connection

# Cached TF-IDF index. Rebuilding tokenizes every concept, which is far too
# expensive to repeat per request, so the index is reused until a concept
# write invalidates it (see invalidate_cache, called from knowledge.py).
_CACHE_EMPTY = object()  # sentinel distinct from any real category key
_index_cache = {"category": _CACHE_EMPTY, "index": {}, "doc_terms": {}, "doc_count": 0}


def invalidate_cache():
    """Drop the cached index so the next search rebuilds it."""
    _index_cache["category"] = _CACHE_EMPTY


def _tokenize(text):
    """Tokenize Latin words and overlapping Chinese bigrams for stdlib search."""
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    for block in re.findall(r"[一-鿿]+", text):
        tokens.append(block)
        tokens.extend(block[i:i + 2] for i in range(len(block) - 1))
    return tokens


def _build_index(category=None):
    """Build (or return cached) term → {doc_id → tf} map from all concepts."""
    if _index_cache["category"] == category:
        return _index_cache["index"], _index_cache["doc_terms"], _index_cache["doc_count"]

    with connection() as conn:
        if category:
            rows = conn.execute(
                "SELECT id, name, description, category, tags FROM concepts WHERE category = ?",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT id, name, description, category, tags FROM concepts").fetchall()

    doc_count = len(rows)
    if doc_count == 0:
        index, doc_terms = {}, {}
    else:
        index = {}          # term → {doc_id: tf}
        doc_terms = {}      # doc_id → [terms]
        for row in rows:
            doc_id = row["id"]
            text = f"{row['name']} {row['description']} {row['category']} {row['tags']}"
            terms = _tokenize(text)
            doc_terms[doc_id] = terms
            tf = Counter(terms)
            for term, count in tf.items():
                index.setdefault(term, {})[doc_id] = count

    _index_cache.update(category=category, index=index, doc_terms=doc_terms, doc_count=doc_count)
    return index, doc_terms, doc_count


def _score_all(query, category=None):
    """Return the full ranked [(doc_id, score)] list for a query."""
    index, doc_terms, doc_count = _build_index(category)
    if doc_count == 0:
        return []

    query_terms = _tokenize(query)
    if not query_terms:
        return []

    # Compute IDF for query terms
    idf = {}
    for term in query_terms:
        df = len(index.get(term, {}))
        idf[term] = math.log((doc_count + 1) / (df + 1)) + 1 if df > 0 else 0

    # Score each document
    scores = {}
    for doc_id, terms in doc_terms.items():
        doc_tf = Counter(terms)
        doc_len = len(terms)
        score = 0.0
        for qterm in query_terms:
            if qterm not in index:
                continue
            tf = doc_tf.get(qterm, 0) / max(doc_len, 1)
            score += tf * idf[qterm]
        if score > 0:
            scores[doc_id] = score

    return sorted(scores.items(), key=lambda x: -x[1])


def _fetch_items(ranked):
    """Fetch concept rows for ranked doc_ids, keeping relevance order."""
    if not ranked:
        return []
    score_map = dict(ranked)
    placeholders = ",".join("?" for _ in ranked)
    with connection() as conn:
        rows = conn.execute(
            f"SELECT id, name, description, category FROM concepts WHERE id IN ({placeholders})",
            [doc_id for doc_id, _ in ranked],
        ).fetchall()
    row_map = {row["id"]: row for row in rows}
    results = []
    for doc_id, _ in ranked:
        row = row_map.get(doc_id)
        if row:
            item = dict(row)
            item["score"] = round(score_map[doc_id], 4)
            results.append(item)
    return results


def search(query, top_k=20, category=None):
    """Return list of {id, name, description, category, score} sorted by TF-IDF relevance."""
    ranked = _score_all(query, category)[:top_k]
    return _fetch_items(ranked)


def search_page(query, limit, offset, category=None):
    """Return (items, total) for one page of matches, ordered by relevance."""
    ranked = _score_all(query, category)
    total = len(ranked)
    return _fetch_items(ranked[offset:offset + limit]), total
