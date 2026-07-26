"""Claim-aware evidence analysis for the local knowledge graph."""
import re

from database import connection, row_dict
from knowledge import RELATION_LABELS
from papers import get_concept_papers


PREDICATE_PATTERNS = (
    ("part_of", r"(?:组成部分|一部分|part\s+of)"),
    ("is_a", r"(?:属于|是.{0,24}(?:一种|一个|一类|子集|分支)|is\s+(?:not\s+)?a|subset\s+of)"),
    ("depends_on", r"(?:依赖|取决于|基于|需要|depends?\s+on|requires?)"),
    ("contradicts", r"(?:矛盾|冲突|不兼容|contradicts?|conflicts?\s+with)"),
    ("causes", r"(?:导致|引起|造成|加速|causes?|leads?\s+to)"),
    ("supports", r"(?:支持|证明|验证|有助于|supports?|evidence\s+for)"),
    ("related_to", r"(?:相关|关联|联系|related\s+to|associated\s+with)"),
)

NEGATION_PATTERN = re.compile(
    r"(?:不依赖|不属于|不是|并非|无关|不相关|不支持|不会导致|不能证明|does\s+not|doesn't|is\s+not|not\s+related)",
    re.IGNORECASE,
)
SYMMETRIC_RELATIONS = {"related_to", "contradicts"}
TRANSITIVE_RELATIONS = {"is_a", "part_of", "depends_on"}


def parse_claim(statement):
    """Parse a statement into known concept endpoints and a graph predicate."""
    text = " ".join(str(statement or "").strip().split())
    lowered = text.lower()
    with connection() as conn:
        concepts = [row_dict(row) for row in conn.execute(
            "SELECT id, name, category FROM concepts ORDER BY LENGTH(name) DESC"
        ).fetchall()]

    mentions = []
    occupied = []
    for concept in concepts:
        start = lowered.find(concept["name"].lower())
        if start < 0:
            continue
        end = start + len(concept["name"])
        if any(start < used_end and end > used_start for used_start, used_end in occupied):
            continue
        occupied.append((start, end))
        mentions.append((start, concept))
    mentions.sort(key=lambda item: item[0])

    predicate = None
    predicate_span = None
    for relation_type, pattern in PREDICATE_PATTERNS:
        match = re.search(pattern, lowered, re.IGNORECASE)
        if match and (predicate_span is None or match.start() < predicate_span[0]):
            predicate = relation_type
            predicate_span = match.span()

    subject = mentions[0][1] if mentions else None
    object_ = mentions[1][1] if len(mentions) > 1 else None
    return {
        "statement": text,
        "subject": subject,
        "predicate": predicate,
        "predicate_label": RELATION_LABELS.get(predicate, "未识别"),
        "object": object_,
        "negated": bool(NEGATION_PATTERN.search(lowered)),
        "mentioned_concepts": [concept for _, concept in mentions],
        "complete": bool(subject and predicate and object_),
    }


def analyze(statement):
    """Return evidence that is explicitly aligned with the parsed claim."""
    claim = parse_claim(statement)
    supports = []
    contradicts = []
    context_relations = []
    counterexamples = []

    subject = claim["subject"]
    object_ = claim["object"]
    predicate = claim["predicate"]

    if subject and object_:
        relations = _relations_between(subject["id"], object_["id"])
        for relation in relations:
            aligned = relation["source_id"] == subject["id"] and relation["target_id"] == object_["id"]
            if relation["relation_type"] in SYMMETRIC_RELATIONS:
                aligned = True
            item = _relation_item(relation, "direct" if aligned else "reverse")

            if predicate and aligned and relation["relation_type"] == predicate:
                if claim["negated"]:
                    contradicts.append(item)
                else:
                    supports.append(item)
            elif predicate == "contradicts" and relation["relation_type"] == "contradicts":
                (contradicts if claim["negated"] else supports).append(item)
            elif predicate != "contradicts" and relation["relation_type"] == "contradicts":
                contradicts.append(item)
                counterexamples.append(_counterexample(relation))
            elif (
                predicate in ("is_a", "part_of")
                and relation["relation_type"] == predicate
                and not aligned
            ):
                contradicts.append(item)
                counterexamples.append(_counterexample(relation))
            else:
                context_relations.append(item)

        if predicate in TRANSITIVE_RELATIONS and not supports and not claim["negated"]:
            inferred = _find_two_hop_path(subject["id"], object_["id"], predicate)
            if inferred:
                supports.append(inferred)
    elif subject:
        context_relations = [
            _relation_item(relation, "context")
            for relation in _relations_for_concept(subject["id"])[:8]
        ]

    related_papers = _related_papers(claim["mentioned_concepts"])
    context_evidence = _context_evidence(claim["mentioned_concepts"])
    overall_level = _overall_level(supports, contradicts)
    open_questions = _open_questions(claim, supports, contradicts)

    return {
        "parsed_claim": claim,
        "overall_level": overall_level,
        "supports": supports,
        "contradicts": contradicts,
        "counterexamples": counterexamples[:3],
        "context_relations": context_relations[:8],
        "context_evidence": context_evidence[:8],
        "open_questions": open_questions,
        "related_concepts": [concept["name"] for concept in claim["mentioned_concepts"]],
        "related_papers": related_papers[:10],
        "limitations": _limitations(claim, supports, contradicts),
    }


def _relations_between(first_id, second_id):
    with connection() as conn:
        return [row_dict(row) for row in conn.execute(
            """SELECT r.*, cs.name AS source_name, ct.name AS target_name
               FROM relations r
               JOIN concepts cs ON cs.id = r.source_id
               JOIN concepts ct ON ct.id = r.target_id
               WHERE (r.source_id = ? AND r.target_id = ?)
                  OR (r.source_id = ? AND r.target_id = ?)""",
            (first_id, second_id, second_id, first_id),
        ).fetchall()]


def _relations_for_concept(concept_id):
    with connection() as conn:
        return [row_dict(row) for row in conn.execute(
            """SELECT r.*, cs.name AS source_name, ct.name AS target_name
               FROM relations r
               JOIN concepts cs ON cs.id = r.source_id
               JOIN concepts ct ON ct.id = r.target_id
               WHERE r.source_id = ? OR r.target_id = ?
               ORDER BY r.confidence DESC""",
            (concept_id, concept_id),
        ).fetchall()]


def _find_two_hop_path(source_id, target_id, relation_type):
    with connection() as conn:
        row = conn.execute(
            """SELECT r1.*, r2.confidence AS second_confidence,
                      r2.evidence AS second_evidence,
                      cs.name AS source_name, cm.name AS middle_name, ct.name AS target_name
               FROM relations r1
               JOIN relations r2 ON r1.target_id = r2.source_id
               JOIN concepts cs ON cs.id = r1.source_id
               JOIN concepts cm ON cm.id = r1.target_id
               JOIN concepts ct ON ct.id = r2.target_id
               WHERE r1.source_id = ? AND r2.target_id = ?
                 AND r1.relation_type = ? AND r2.relation_type = ?
               ORDER BY MIN(r1.confidence, r2.confidence) DESC LIMIT 1""",
            (source_id, target_id, relation_type, relation_type),
        ).fetchone()
    if not row:
        return None
    row = row_dict(row)
    confidence = min(row["confidence"], row["second_confidence"]) * 0.7
    return {
        "concept": row["target_name"],
        "source_name": row["source_name"],
        "target_name": row["target_name"],
        "relation": relation_type,
        "relation_label": RELATION_LABELS[relation_type],
        "evidence": f"{row['source_name']} -> {row['middle_name']} -> {row['target_name']}",
        "level": _evidence_level(confidence, inferred=True),
        "confidence": round(confidence, 3),
        "match_kind": "inferred",
        "path": [row["source_name"], row["middle_name"], row["target_name"]],
    }


def _relation_item(relation, match_kind):
    return {
        "concept": relation["target_name"],
        "source_name": relation["source_name"],
        "target_name": relation["target_name"],
        "relation": relation["relation_type"],
        "relation_label": RELATION_LABELS.get(relation["relation_type"], relation["relation_type"]),
        "evidence": relation.get("evidence", ""),
        "level": _evidence_level(relation.get("confidence", 0)),
        "confidence": relation.get("confidence", 0),
        "match_kind": match_kind,
    }


def _counterexample(relation):
    return {
        "concept_a": relation["source_name"],
        "relation": RELATION_LABELS.get(relation["relation_type"], relation["relation_type"]),
        "concept_b": relation["target_name"],
        "evidence": relation.get("evidence", ""),
    }


def _related_papers(concepts):
    papers = []
    seen = set()
    for concept in concepts:
        for paper in get_concept_papers(concept["id"]):
            if paper["id"] not in seen:
                seen.add(paper["id"])
                paper["context_for"] = concept["name"]
                papers.append(paper)
    return papers


def _context_evidence(concepts):
    if not concepts:
        return []
    ids = [concept["id"] for concept in concepts]
    placeholders = ",".join("?" for _ in ids)
    with connection() as conn:
        return [row_dict(row) for row in conn.execute(
            f"""SELECT e.*, c.name AS concept_name
                FROM evidence e JOIN concepts c ON c.id = e.concept_id
                WHERE e.concept_id IN ({placeholders}) ORDER BY e.added_at DESC""",
            ids,
        ).fetchall()]


def _open_questions(claim, supports, contradicts):
    if not claim["mentioned_concepts"]:
        return [{"question": "当前陈述没有匹配到知识库中的概念。", "concept": ""}]
    if not claim["complete"]:
        return [{"question": "请用“概念 A + 关系 + 概念 B”的形式补全命题。", "concept": claim["subject"]["name"]}]
    if not supports and not contradicts:
        return [{
            "question": f"是否存在可追溯来源来验证“{claim['subject']['name']} {claim['predicate_label']} {claim['object']['name']}”？",
            "concept": claim["subject"]["name"],
        }]
    return []


def _limitations(claim, supports, contradicts):
    limitations = ["结论只反映当前本地知识库，不代表科学共识。"]
    if not claim["complete"]:
        limitations.append("命题未完整解析，系统不会据此给出方向性结论。")
    if supports and all(not item.get("evidence") or item.get("match_kind") == "inferred" for item in supports):
        limitations.append("匹配关系缺少直接来源或仅为传递推断，需要人工复核。")
    if contradicts and supports:
        limitations.append("当前知识库同时存在支持与反对信号。")
    return limitations


def _overall_level(supports, contradicts):
    items = supports + contradicts
    if not items:
        return "none"
    if any(item["level"] == "strong" and item["match_kind"] == "direct" for item in items):
        return "strong"
    if any(item["match_kind"] == "direct" for item in items):
        return "moderate"
    return "weak"


def _evidence_level(confidence, inferred=False):
    if inferred:
        return "weak" if confidence < 0.65 else "moderate"
    if confidence >= 0.9:
        return "strong"
    if confidence >= 0.65:
        return "moderate"
    return "weak"
