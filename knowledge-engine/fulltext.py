"""Paper full-text chunking and local TF-IDF search."""
import re
import math
from collections import Counter
from database import connection
from papers import get_chunks, add_chunk, get_paper


def chunk_paper(paper_id, text, chunk_size=500, overlap=50):
    """Split text into overlapping chunks and store them."""
    if not text:
        return 0
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("分块大小必须大于重叠长度")
    text = " ".join(str(text).split())
    if not text:
        return 0
    with connection() as conn:
        conn.execute("DELETE FROM paper_chunks WHERE paper_id = ?", (paper_id,))
    count = 0
    step = chunk_size - overlap
    for start in range(0, len(text), step):
        chunk = text[start:start + chunk_size]
        if chunk.strip():
            add_chunk(paper_id, count, chunk)
            count += 1
        if start + chunk_size >= len(text):
            break
    return count


def _tokenize(text):
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    for block in re.findall(r"[一-鿿]+", text.lower()):
        if len(block) > 1:
            tokens.append(block)
            tokens.extend(block[j:j + 2] for j in range(len(block) - 1))
        else:
            tokens.append(block)
    return tokens


def _chunk_signature():
    """Cheap DB signature for cache invalidation: chunks are only ever
    deleted and re-inserted, so rowid bounds/count change on every write."""
    with connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c, COALESCE(MIN(rowid), 0) AS lo, COALESCE(MAX(rowid), 0) AS hi FROM paper_chunks"
        ).fetchone()
    return (row["c"], row["lo"], row["hi"])


_index_cache = {"signature": None, "index": {}, "doc_terms": {}}


def build_index():
    """Build (or reuse cached) TF-IDF index over all paper chunks."""
    signature = _chunk_signature()
    if _index_cache["signature"] == signature:
        return _index_cache["index"], _index_cache["doc_terms"]

    with connection() as conn:
        rows = conn.execute("SELECT id, content FROM paper_chunks").fetchall()

    doc_count = len(rows)
    if doc_count == 0:
        index, doc_terms = {}, {}
    else:
        index = {}
        doc_terms = {}
        for row in rows:
            doc_id = row["id"]
            terms = _tokenize(row["content"])
            doc_terms[doc_id] = terms
            tf = Counter(terms)
            for term, count in tf.items():
                index.setdefault(term, set()).add(doc_id)

    _index_cache.update(signature=signature, index=index, doc_terms=doc_terms)
    return index, doc_terms


def search(query, top_k=20):
    """Search paper chunks by TF-IDF relevance. Returns list of chunk results."""
    index, doc_terms = build_index()
    if not index:
        return []

    query_terms = _tokenize(query)
    if not query_terms:
        return []

    doc_count = len(doc_terms)
    idf = {}
    for term in query_terms:
        df = len(index.get(term, set()))
        idf[term] = math.log((doc_count + 1) / (df + 1)) + 1 if df > 0 else 0

    scores = {}
    for doc_id, terms in doc_terms.items():
        doc_tf = Counter(terms)
        doc_len = len(terms)
        score = 0.0
        for qterm in query_terms:
            if qterm not in index:
                continue
            tf = doc_tf.get(qterm, 0) / max(doc_len, 1)
            score += tf * idf.get(qterm, 0)
        if score > 0:
            scores[doc_id] = score

    ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]

    if not ranked:
        return []
    score_map = dict(ranked)
    placeholders = ",".join("?" for _ in ranked)
    with connection() as conn:
        rows = conn.execute(
            f"""SELECT pc.*, p.title AS paper_title, p.authors AS paper_authors
                FROM paper_chunks pc JOIN papers p ON p.id = pc.paper_id
                WHERE pc.id IN ({placeholders})""",
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
