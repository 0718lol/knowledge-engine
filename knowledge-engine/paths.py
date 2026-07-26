"""Research path generation and user selection tracking."""
import json

from database import connection, row_dict, rows_dict, new_id, now_iso
from knowledge import get_concept


def generate(analysis, hypothesis_id=None):
    """Create distinct claim, counterevidence, context, and literature paths."""
    if hypothesis_id:
        existing = get_paths_for_hypothesis(hypothesis_id)
        if existing:
            return [_serialize_path(path) for path in existing]

    claim = analysis.get("parsed_claim") or {}
    mentioned = claim.get("mentioned_concepts") or []
    claim_ids = _unique([concept.get("id") for concept in mentioned if concept.get("id")])
    if not claim_ids:
        return []

    specs = []
    supports = analysis.get("supports") or []
    contradicts = analysis.get("contradicts") or []
    context = analysis.get("context_relations") or []
    related_papers = analysis.get("related_papers") or []

    support_ids = _ids_for_relation_items(supports)
    specs.append({
        "path_label": "命题证据路径" if supports else "命题核查路径",
        "description": "复核命题两端的直接关系与传递路径" if supports else "围绕命题两端补充尚缺失的直接证据",
        "concept_ids": _unique(claim_ids + support_ids),
        "paper_ids": [],
    })

    if contradicts:
        specs.append({
            "path_label": "反证与边界路径",
            "description": "检查方向相反或与命题冲突的知识关系",
            "concept_ids": _unique(claim_ids + _ids_for_relation_items(contradicts)),
            "paper_ids": [],
        })
    else:
        context_ids = _ids_for_relation_items(context)
        if context_ids:
            specs.append({
                "path_label": "邻接概念路径",
                "description": "沿命题概念的一跳关系探索适用边界",
                "concept_ids": _unique(claim_ids + context_ids)[:8],
                "paper_ids": [],
            })

    paper_ids = _unique([paper.get("id") for paper in related_papers if paper.get("id")])
    if paper_ids:
        specs.append({
            "path_label": "相关阅读路径",
            "description": "阅读相关论文并人工判断其是否真正支持命题",
            "concept_ids": claim_ids,
            "paper_ids": paper_ids,
        })

    if len(specs) < 2:
        neighbor_ids = _neighbor_ids(claim_ids)
        if neighbor_ids:
            specs.append({
                "path_label": "领域扩展路径",
                "description": "从同领域相邻节点寻找新的可验证关系",
                "concept_ids": _unique(claim_ids + neighbor_ids)[:8],
                "paper_ids": [],
            })

    result = []
    for spec in specs[:3]:
        if not spec["paper_ids"]:
            spec["paper_ids"] = _paper_ids_for_concepts(spec["concept_ids"])
        path_id = new_id()
        with connection() as conn:
            conn.execute(
                """INSERT INTO research_paths
                   (id, hypothesis_id, path_label, description, concepts, papers, is_selected, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    path_id, hypothesis_id, spec["path_label"], spec["description"],
                    json.dumps(spec["concept_ids"]), json.dumps(spec["paper_ids"]), now_iso(),
                ),
            )
            row = row_dict(conn.execute("SELECT * FROM research_paths WHERE id = ?", (path_id,)).fetchone())
        result.append(_serialize_path(row))
    return result


def select_path(path_id, note=""):
    """Mark one path as selected for its hypothesis."""
    with connection() as conn:
        path = conn.execute("SELECT * FROM research_paths WHERE id = ?", (path_id,)).fetchone()
        if not path:
            return None
        if path["hypothesis_id"] is not None:
            conn.execute(
                "UPDATE research_paths SET is_selected = 0 WHERE hypothesis_id = ?",
                (path["hypothesis_id"],),
            )
        conn.execute(
            "UPDATE research_paths SET is_selected = 1, decision_note = ? WHERE id = ?",
            (note, path_id),
        )
        row = row_dict(conn.execute("SELECT * FROM research_paths WHERE id = ?", (path_id,)).fetchone())
    return _serialize_path(row)


def get_paths_for_hypothesis(hypothesis_id):
    with connection() as conn:
        return rows_dict(conn.execute(
            "SELECT * FROM research_paths WHERE hypothesis_id = ? ORDER BY created_at, rowid",
            (hypothesis_id,),
        ).fetchall())


def get_path(path_id):
    with connection() as conn:
        row = row_dict(conn.execute("SELECT * FROM research_paths WHERE id = ?", (path_id,)).fetchone())
    return _serialize_path(row) if row else None


def _serialize_path(path):
    concept_ids = path.get("concepts", path.get("concept_ids", [])) or []
    paper_ids = path.get("papers", path.get("paper_ids", [])) or []
    item = dict(path)
    item["concept_ids"] = concept_ids
    item["paper_ids"] = paper_ids
    item["is_selected"] = bool(item.get("is_selected"))
    item["concept_names"] = []
    for concept_id in concept_ids:
        concept = get_concept(concept_id)
        if concept:
            item["concept_names"].append(concept["name"])
    return item


def _ids_for_relation_items(items):
    names = []
    for item in items:
        names.extend((item.get("source_name"), item.get("target_name"), item.get("concept")))
    names = _unique([name for name in names if name])
    if not names:
        return []
    placeholders = ",".join("?" for _ in names)
    with connection() as conn:
        rows = conn.execute(
            f"SELECT id, name FROM concepts WHERE name IN ({placeholders})",
            names,
        ).fetchall()
    id_by_name = {row["name"]: row["id"] for row in rows}
    return [id_by_name[name] for name in names if name in id_by_name]


def _neighbor_ids(concept_ids):
    placeholders = ",".join("?" for _ in concept_ids)
    with connection() as conn:
        rows = conn.execute(
            f"""SELECT source_id, target_id FROM relations
                WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})
                ORDER BY confidence DESC LIMIT 12""",
            concept_ids + concept_ids,
        ).fetchall()
    neighbors = []
    concept_set = set(concept_ids)
    for row in rows:
        if row["source_id"] not in concept_set:
            neighbors.append(row["source_id"])
        if row["target_id"] not in concept_set:
            neighbors.append(row["target_id"])
    return _unique(neighbors)


def _paper_ids_for_concepts(concept_ids):
    if not concept_ids:
        return []
    placeholders = ",".join("?" for _ in concept_ids)
    with connection() as conn:
        rows = conn.execute(
            f"SELECT paper_id FROM paper_concepts WHERE concept_id IN ({placeholders})",
            concept_ids,
        ).fetchall()
    return _unique([row["paper_id"] for row in rows])


def _unique(values):
    return list(dict.fromkeys(value for value in values if value))
