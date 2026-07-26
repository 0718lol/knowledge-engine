"""Assemble a local, source-aware research brief for a user question."""
from database import connection, rows_dict
from issues import get_issue, match_claims
from papers import get_concept_papers
from search import search


def build(question):
    question = " ".join(str(question or "").strip().split())
    if not question:
        raise ValueError("研究问题不能为空")

    concepts = [
        item for item in search(question, top_k=8)
        if item.get("score", 0) >= .18 or item["name"].lower() in question.lower()
    ]
    claim_matches = match_claims(question, limit=4)
    issue = get_issue(claim_matches[0]["issue_id"]) if claim_matches else None

    if issue:
        known_ids = {item["id"] for item in concepts}
        for concept in issue["concepts"]:
            if concept["id"] not in known_ids:
                concepts.append(concept)
                known_ids.add(concept["id"])
    concepts = concepts[:10]
    concept_ids = [item["id"] for item in concepts]

    relations = _relations(concept_ids)
    evidence = _evidence(concept_ids)
    papers = _papers(concepts)
    open_questions = _open_questions(concept_ids)
    curated_claims = issue["claims"] if issue else claim_matches

    if issue:
        assessment = issue["current_assessment"]
        status = "curated"
        limitation = "当前判断来自已策展专题；命题级证据用于展示边界，不替代原始论文与人工复核。"
    elif concepts:
        assessment = f"本地知识库找到了 {len(concepts)} 个相关概念，但尚无足够的策展命题形成条件化判断。"
        status = "exploratory"
        limitation = "这是一份探索性索引，不是结论。需要补充可区分支持与反对方向的命题级证据。"
    else:
        assessment = "当前本地知识库没有找到足够相关的概念。"
        status = "insufficient"
        limitation = "知识覆盖不足；系统没有根据相似措辞生成推测性答案。"

    return {
        "question": question,
        "status": status,
        "assessment": assessment,
        "limitation": limitation,
        "issue": {"id": issue["id"], "title": issue["title"]} if issue else None,
        "concepts": concepts,
        "claims": curated_claims[:6],
        "relations": relations[:10],
        "evidence": evidence[:10],
        "papers": papers[:8],
        "open_questions": open_questions[:8],
        "coverage": {
            "concepts": len(concepts),
            "claims": len(curated_claims),
            "relations": len(relations),
            "sources": len(evidence) + len(papers),
        },
    }


def _relations(concept_ids):
    if not concept_ids:
        return []
    placeholders = ",".join("?" for _ in concept_ids)
    params = concept_ids + concept_ids
    with connection() as conn:
        return rows_dict(conn.execute(
            f"""SELECT r.*, cs.name AS source_name, ct.name AS target_name
                FROM relations r
                JOIN concepts cs ON cs.id = r.source_id
                JOIN concepts ct ON ct.id = r.target_id
                WHERE r.source_id IN ({placeholders}) OR r.target_id IN ({placeholders})
                ORDER BY r.confidence DESC, r.created_at DESC""",
            params,
        ).fetchall())


def _evidence(concept_ids):
    if not concept_ids:
        return []
    placeholders = ",".join("?" for _ in concept_ids)
    with connection() as conn:
        return rows_dict(conn.execute(
            f"""SELECT e.*, c.name AS concept_name
                FROM evidence e JOIN concepts c ON c.id = e.concept_id
                WHERE e.concept_id IN ({placeholders}) ORDER BY e.added_at DESC""",
            concept_ids,
        ).fetchall())


def _papers(concepts):
    results = []
    seen = set()
    for concept in concepts:
        for paper in get_concept_papers(concept["id"]):
            if paper["id"] in seen:
                continue
            seen.add(paper["id"])
            paper["context_for"] = concept["name"]
            results.append(paper)
    results.sort(key=lambda item: (item.get("year") or 0, item.get("added_at") or ""), reverse=True)
    return results


def _open_questions(concept_ids):
    if not concept_ids:
        return []
    placeholders = ",".join("?" for _ in concept_ids)
    with connection() as conn:
        return rows_dict(conn.execute(
            f"""SELECT cs.content AS question, c.id AS concept_id, c.name AS concept_name
                FROM concept_sections cs JOIN concepts c ON c.id = cs.concept_id
                WHERE cs.concept_id IN ({placeholders}) AND cs.section_type = 'question'
                ORDER BY cs.sort_order, c.name""",
            concept_ids,
        ).fetchall())
