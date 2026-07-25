"""Strict evidence analysis engine: levels, counterexamples, open questions."""
import re
from database import connection
from knowledge import list_concepts, get_concept
from papers import get_concept_papers


def _tokenize(text):
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    for block in re.findall(r"[一-鿿]+", text.lower()):
        tokens.add(block)
        tokens.update(block[i:i + 2] for i in range(len(block) - 1))
    return tokens


def analyze(statement):
    """Given a hypothesis statement, produce a structured evidence analysis.

    Returns dict with:
      - overall_level: 'strong' | 'moderate' | 'weak' | 'none'
      - supports: list of {concept, relation, evidence, level, paper}
      - contradicts: list of {concept, relation, evidence, level, paper}
      - counterexamples: list of {concept_a, relation, concept_b, evidence}
      - open_questions: list of {concept, question, related_evidence_count}
      - related_concepts: list of concept names
      - related_papers: list of paper dicts
    """
    tokens = _tokenize(statement)
    # Search for related concepts
    with connection() as conn:
        all_concepts = rows_dict(conn.execute("SELECT * FROM concepts").fetchall())

    # Score concepts by token overlap
    scored = []
    for c in all_concepts:
        ctokens = _tokenize(f"{c['name']} {c['description']} {c.get('category', '')}")
        overlap = tokens & ctokens
        if overlap:
            scored.append((c, len(overlap) / max(len(tokens), 1)))
    scored.sort(key=lambda x: -x[1])
    top_concepts = [c for c, _ in scored[:5]]

    if not top_concepts:
        return {
            "overall_level": "none",
            "supports": [],
            "contradicts": [],
            "counterexamples": [],
            "open_questions": [],
            "related_concepts": [],
            "related_papers": [],
        }

    # Gather relations and papers for top concepts
    concept_ids = [c["id"] for c in top_concepts]
    supports = []
    contradicts = []
    counterexamples = []
    open_questions = []
    seen_paper_ids = set()

    with connection() as conn:
        for cid in concept_ids:
            # Relations
            rels = conn.execute(
                """SELECT r.*, cs.name AS source_name, ct.name AS target_name
                   FROM relations r
                   JOIN concepts cs ON cs.id = r.source_id
                   JOIN concepts ct ON ct.id = r.target_id
                   WHERE r.source_id = ? OR r.target_id = ?""",
                (cid, cid)
            ).fetchall()

            for r in rels:
                item = {
                    "concept": r["source_name"] if r["source_id"] != cid else r["target_name"],
                    "relation": r["relation_type"],
                    "evidence": r["evidence"],
                    "level": _evidence_level(r["confidence"]),
                    "paper": "",
                }
                if r["relation_type"] in ("supports", "causes", "is_a", "part_of"):
                    supports.append(item)
                elif r["relation_type"] == "contradicts":
                    contradicts.append(item)
                    counterexamples.append({
                        "concept_a": r["source_name"],
                        "relation": r["relation_type"],
                        "concept_b": r["target_name"],
                        "evidence": r["evidence"],
                    })

    # Get papers linked to top concepts
    related_papers = []
    for cid in concept_ids:
        for p in get_concept_papers(cid):
            if p["id"] not in seen_paper_ids:
                seen_paper_ids.add(p["id"])
                related_papers.append(p)
                # Add evidence from paper abstract
                if p.get("abstract"):
                    level = "strong" if p.get("year") and p["year"] >= 2020 else "moderate"
                    supports.append({
                        "concept": p.get("title", "论文")[:60],
                        "relation": "evidence",
                        "evidence": p["abstract"][:200],
                        "level": level,
                        "paper": p["title"],
                    })

    # Determine open questions: concepts in same category but not directly related
    with connection() as conn:
        for c in top_concepts:
            others = conn.execute(
                """SELECT id, name FROM concepts
                   WHERE category = ? AND id != ? AND id NOT IN (
                       SELECT target_id FROM relations WHERE source_id = ?
                       UNION SELECT source_id FROM relations WHERE target_id = ?
                   ) LIMIT 3""",
                (c["category"], c["id"], c["id"], c["id"])
            ).fetchall()
            for other in others:
                open_questions.append({
                    "concept": other["name"],
                    "question": f"{c['name']} 与 {other['name']} 之间是否存在未发现的关系？",
                    "related_evidence_count": 0,
                })

    # Overall level
    support_scores = [s["evidence"] for s in supports if s["evidence"]]
    contradict_scores = [c["evidence"] for c in contradicts if c["evidence"]]
    if len(support_scores) >= 3 and len(support_scores) > len(contradict_scores) * 2:
        overall_level = "strong"
    elif len(support_scores) >= 1 or len(related_papers) >= 2:
        overall_level = "moderate"
    elif len(support_scores) > 0:
        overall_level = "weak"
    else:
        overall_level = "none"

    return {
        "overall_level": overall_level,
        "supports": supports[:8],
        "contradicts": contradicts[:5],
        "counterexamples": counterexamples[:3],
        "open_questions": open_questions[:5],
        "related_concepts": [c["name"] for c in top_concepts],
        "related_papers": related_papers[:10],
    }


def _evidence_level(confidence):
    if confidence >= 0.8:
        return "strong"
    elif confidence >= 0.5:
        return "moderate"
    return "weak"


def rows_dict(rows):
    from database import row_dict
    return [row_dict(r) for r in rows]