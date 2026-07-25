"""Hypothesis verification engine: given a statement, find supporting / contradicting evidence."""
import re
from database import connection
from search import search


def _tokenize(text):
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    for block in re.findall(r"[一-鿿]+", text.lower()):
        tokens.add(block)
        tokens.update(block[i:i + 2] for i in range(len(block) - 1))
    return tokens


def verify(statement):
    """Evaluate a hypothesis statement. Returns a verdict dict."""
    tokens = _tokenize(statement)
    related = search(statement, top_k=10)

    if not related:
        result = create_hypothesis(statement, "unknown", 0, [])
        return result

    with connection() as conn:
        # Collect all relations involving the top related concepts
        ids = tuple(r["id"] for r in related)
        if len(ids) == 1:
            ids = (ids[0], ids[0])
        rels = conn.execute(
            f"""SELECT r.*, cs.name AS source_name, ct.name AS target_name
                FROM relations r
                JOIN concepts cs ON cs.id = r.source_id
                JOIN concepts ct ON ct.id = r.target_id
                WHERE r.source_id IN ({','.join('?' * len(ids))})
                   OR r.target_id IN ({','.join('?' * len(ids))})""",
            (*ids, *ids)
        ).fetchall()

    supports = []
    contradicts = []
    unknown = []

    for rel in rels:
        rel_tokens = _tokenize(f"{rel['source_name']} {rel['target_name']} {rel['relation_type']} {rel['evidence']}")
        overlap = tokens & rel_tokens
        if not overlap:
            continue
        item = {
            "source": rel["source_name"],
            "target": rel["target_name"],
            "type": rel["relation_type"],
            "evidence": rel["evidence"],
            "confidence": rel["confidence"],
        }
        if rel["relation_type"] in ("supports", "causes", "is_a", "part_of"):
            supports.append(item)
        elif rel["relation_type"] in ("contradicts",):
            contradicts.append(item)
        else:
            unknown.append(item)

    # Also add related concepts' descriptions as supporting context
    for r in related:
        desc_tokens = _tokenize(r["description"])
        if tokens & desc_tokens:
            supports.append({
                "source": r["name"],
                "target": statement,
                "type": "related",
                "evidence": r["description"][:200],
                "confidence": r.get("score", 0.5),
            })

    # Determine verdict
    support_score = sum(s["confidence"] for s in supports)
    contradict_score = sum(c["confidence"] for c in contradicts)

    if support_score > contradict_score * 1.5:
        result = "supports"
        confidence = min(1.0, support_score / (support_score + contradict_score + 0.1))
    elif contradict_score > support_score * 1.5:
        result = "contradicts"
        confidence = min(1.0, contradict_score / (support_score + contradict_score + 0.1))
    else:
        result = "inconclusive"
        confidence = 0.5

    evidence_summary = {
        "supports": supports[:5],
        "contradicts": contradicts[:5],
        "unknown": unknown[:5],
        "related_concepts": [r["name"] for r in related[:5]],
    }

    return create_hypothesis(statement, result, round(confidence, 3), evidence_summary)


def create_hypothesis(statement, result, confidence, evidence_summary):
    from knowledge import create_hypothesis as _create
    return _create(statement, result, confidence, evidence_summary)