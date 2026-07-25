"""Research path generation and user selection tracking."""
import json
from database import connection, row_dict, rows_dict, new_id, now_iso
from knowledge import get_concept, list_concepts


def generate(analysis, hypothesis_id=None):
    """Generate 2-3 distinct research paths based on evidence analysis.

    Each path is a cluster of related concepts and papers that form a coherent
    exploration direction. Returns list of path dicts.
    """
    concepts = analysis.get("related_concepts", [])
    papers = analysis.get("related_papers", [])
    supports = analysis.get("supports", [])
    contradicts = analysis.get("contradicts", [])

    if not concepts:
        return []

    with connection() as conn:
        all_concepts = rows_dict(conn.execute("SELECT * FROM concepts").fetchall())

    # Build concept map
    concept_map = {c["name"]: c for c in all_concepts}

    # Group concepts by category for path diversity
    by_category = {}
    for name in concepts:
        c = concept_map.get(name)
        if c:
            by_category.setdefault(c.get("category", "未分类"), []).append(c["name"])

    paths = []
    path_labels = []

    # Path 1: Core evidence path (strongest supports)
    if supports:
        support_names = set()
        for s in supports[:5]:
            if s.get("concept"):
                support_names.add(s["concept"])
        path_concepts = []
        for name in support_names:
            c = concept_map.get(name)
            if c:
                path_concepts.append(c["id"])
        if path_concepts:
            path_labels.append(("核心证据路径", "沿着支持假设的最强证据链深入探索"))
            paths.append(path_concepts)

    # Path 2: Contradiction / frontier path
    if contradicts:
        contra_names = set()
        for c in contradicts[:3]:
            if c.get("concept"):
                contra_names.add(c["concept"])
        path_concepts = []
        for name in contra_names:
            c = concept_map.get(name)
            if c:
                path_concepts.append(c["id"])
        if path_concepts:
            path_labels.append(("矛盾与前沿路径", "探索与假设相矛盾的证据，理解争议边界"))
            paths.append(path_concepts)

    # Path 3: Under-explored / open questions path
    open_questions = analysis.get("open_questions", [])
    if open_questions:
        oq_names = [oq["concept"] for oq in open_questions if oq.get("concept")]
        path_concepts = []
        for name in oq_names:
            c = concept_map.get(name)
            if c:
                path_concepts.append(c["id"])
        if path_concepts:
            path_labels.append(("开放问题路径", "探索尚未与假设建立直接联系的相关概念"))
            paths.append(path_concepts)

    # If we still don't have 2 paths, add category-based fallback
    if len(paths) < 2:
        for category, names in by_category.items():
            cids = []
            for name in names:
                c = concept_map.get(name)
                if c:
                    cids.append(c["id"])
            if cids and cids not in paths:
                path_labels.append((f"{category}探索路径", f"从{category}领域深入探索相关概念"))
                paths.append(cids)

    # Build result
    result = []
    for i, (label, desc) in enumerate(path_labels[:3]):
        cids = paths[i] if i < len(paths) else []
        # Get paper IDs linked to these concepts
        paper_ids = []
        with connection() as conn:
            for cid in cids:
                pc = conn.execute(
                    "SELECT paper_id FROM paper_concepts WHERE concept_id = ?", (cid,)
                ).fetchall()
                for row in pc:
                    if row["paper_id"] not in paper_ids:
                        paper_ids.append(row["paper_id"])

        path_data = {
            "path_label": label,
            "description": desc,
            "concept_ids": cids,
            "paper_ids": paper_ids,
            "is_selected": False,
            "decision_note": "",
        }

        # Save to database
        now = now_iso()
        pid = new_id()
        with connection() as conn:
            conn.execute(
                """INSERT INTO research_paths (id, hypothesis_id, path_label, description, concepts, papers, is_selected, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
                (pid, hypothesis_id, label, desc, json.dumps(cids), json.dumps(paper_ids), now)
            )
            row = conn.execute("SELECT * FROM research_paths WHERE id = ?", (pid,)).fetchone()
        path_data["id"] = row["id"]
        # Load concept names
        path_data["concept_names"] = []
        for cid in cids:
            c = get_concept(cid)
            if c:
                path_data["concept_names"].append(c["name"])
        result.append(path_data)

    return result


def select_path(path_id, note=""):
    """Mark a research path as selected by the user."""
    with connection() as conn:
        # Unselect all paths for this hypothesis
        path = conn.execute("SELECT * FROM research_paths WHERE id = ?", (path_id,)).fetchone()
        if not path:
            return None
        conn.execute(
            "UPDATE research_paths SET is_selected = 0 WHERE hypothesis_id = ?",
            (path["hypothesis_id"],)
        )
        # Select this one
        conn.execute(
            "UPDATE research_paths SET is_selected = 1, decision_note = ? WHERE id = ?",
            (note, path_id)
        )
        row = conn.execute("SELECT * FROM research_paths WHERE id = ?", (path_id,)).fetchone()
    return row_dict(row)


def get_paths_for_hypothesis(hypothesis_id):
    with connection() as conn:
        return rows_dict(conn.execute(
            "SELECT * FROM research_paths WHERE hypothesis_id = ? ORDER BY created_at",
            (hypothesis_id,)
        ).fetchall())


def get_path(path_id):
    with connection() as conn:
        return row_dict(conn.execute("SELECT * FROM research_paths WHERE id = ?", (path_id,)).fetchone())