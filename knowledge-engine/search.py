"""Pure-Python TF-IDF text search over concepts."""
import math
import re
from collections import Counter
from database import connection


def _tokenize(text):
    """Tokenize Latin words and overlapping Chinese bigrams for stdlib search."""
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    for block in re.findall(r"[一-鿿]+", text):
        tokens.append(block)
        tokens.extend(block[i:i + 2] for i in range(len(block) - 1))
    return tokens


def _build_index():
    """Build a term → {doc_id → tf} map from all concepts."""
    with connection() as conn:
        rows = conn.execute("SELECT id, name, description, category, tags FROM concepts").fetchall()

    doc_count = len(rows)
    if doc_count == 0:
        return {}, [], 0

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

    return index, doc_terms, doc_count


def search(query, top_k=20):
    """Return list of {id, name, description, category, score} sorted by TF-IDF relevance."""
    index, doc_terms, doc_count = _build_index()
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

    # Get top-k
    ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]

    with connection() as conn:
        results = []
        for doc_id, score in ranked:
            row = conn.execute(
                "SELECT id, name, description, category FROM concepts WHERE id = ?",
                (doc_id,)
            ).fetchone()
            if row:
                item = dict(row)
                item["score"] = round(score, 4)
                results.append(item)
    return results