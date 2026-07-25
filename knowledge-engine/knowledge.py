"""Concept, relation, and evidence CRUD operations."""
from database import connection, row_dict, rows_dict, new_id, now_iso
import json


# ─── Concepts ───────────────────────────────────────────────────────────────────

def list_concepts(q=None, category=None, limit=50, offset=0):
    with connection() as conn:
        if q:
            return rows_dict(conn.execute(
                """SELECT * FROM concepts WHERE name LIKE ? OR description LIKE ?
                   ORDER BY updated_at DESC LIMIT ? OFFSET ?""",
                (f"%{q}%", f"%{q}%", limit, offset)
            ).fetchall())
        if category:
            return rows_dict(conn.execute(
                "SELECT * FROM concepts WHERE category = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (category, limit, offset)
            ).fetchall())
        return rows_dict(conn.execute(
            "SELECT * FROM concepts ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall())


def get_concept(concept_id):
    with connection() as conn:
        return row_dict(conn.execute(
            "SELECT * FROM concepts WHERE id = ?", (concept_id,)
        ).fetchone())


def get_concept_by_name(name):
    with connection() as conn:
        return row_dict(conn.execute(
            "SELECT * FROM concepts WHERE name = ?", (name,)
        ).fetchone())


def create_concept(name, description, category="未分类", tags=None, source=""):
    now = now_iso()
    cid = new_id()
    with connection() as conn:
        conn.execute(
            """INSERT INTO concepts (id, name, description, category, tags, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (cid, name, description, category, json.dumps(tags or []), source, now, now)
        )
    return get_concept(cid)


def update_concept(concept_id, **kwargs):
    allowed = {"name", "description", "category", "tags", "source"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_concept(concept_id)
    updates["updated_at"] = now_iso()
    if "tags" in updates and isinstance(updates["tags"], list):
        updates["tags"] = json.dumps(updates["tags"])
    cols = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [concept_id]
    with connection() as conn:
        conn.execute(f"UPDATE concepts SET {cols} WHERE id = ?", vals)
    return get_concept(concept_id)


def delete_concept(concept_id):
    with connection() as conn:
        conn.execute("DELETE FROM concepts WHERE id = ?", (concept_id,))


# ─── Relations ──────────────────────────────────────────────────────────────────

def list_relations(concept_id=None, limit=200):
    with connection() as conn:
        if concept_id:
            return rows_dict(conn.execute(
                """SELECT r.*, cs.name AS source_name, ct.name AS target_name
                   FROM relations r
                   JOIN concepts cs ON cs.id = r.source_id
                   JOIN concepts ct ON ct.id = r.target_id
                   WHERE r.source_id = ? OR r.target_id = ?
                   ORDER BY r.created_at DESC LIMIT ?""",
                (concept_id, concept_id, limit)
            ).fetchall())
        return rows_dict(conn.execute(
            """SELECT r.*, cs.name AS source_name, ct.name AS target_name
               FROM relations r
               JOIN concepts cs ON cs.id = r.source_id
               JOIN concepts ct ON ct.id = r.target_id
               ORDER BY r.created_at DESC LIMIT ?""",
            (limit,)
        ).fetchall())


def create_relation(source_id, target_id, relation_type, evidence="", confidence=0.5):
    now = now_iso()
    rid = new_id()
    with connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO relations
               (id, source_id, target_id, relation_type, evidence, confidence, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (rid, source_id, target_id, relation_type, evidence, confidence, now)
        )
    return list_relations()  # find the one we just inserted


def get_relation_types():
    return ["causes", "contradicts", "supports", "is_a", "part_of", "example", "related_to", "depends_on"]


def delete_relation(relation_id):
    with connection() as conn:
        conn.execute("DELETE FROM relations WHERE id = ?", (relation_id,))


# ─── Evidence ───────────────────────────────────────────────────────────────────

def list_evidence(concept_id=None, limit=100):
    with connection() as conn:
        if concept_id:
            return rows_dict(conn.execute(
                "SELECT * FROM evidence WHERE concept_id = ? ORDER BY added_at DESC LIMIT ?",
                (concept_id, limit)
            ).fetchall())
        return rows_dict(conn.execute(
            "SELECT * FROM evidence ORDER BY added_at DESC LIMIT ?", (limit,)
        ).fetchall())


def create_evidence(concept_id, content, source_url="", source_title=""):
    now = now_iso()
    eid = new_id()
    with connection() as conn:
        conn.execute(
            """INSERT INTO evidence (id, concept_id, content, source_url, source_title, added_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (eid, concept_id, content, source_url, source_title, now)
        )
        row = conn.execute("SELECT * FROM evidence WHERE id = ?", (eid,)).fetchone()
    return row_dict(row)


# ─── Hypotheses ─────────────────────────────────────────────────────────────────

def list_hypotheses(limit=20):
    with connection() as conn:
        return rows_dict(conn.execute(
            "SELECT * FROM hypotheses ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall())


def create_hypothesis(statement, result, confidence, evidence_summary):
    now = now_iso()
    hid = new_id()
    with connection() as conn:
        conn.execute(
            """INSERT INTO hypotheses (id, statement, result, confidence, evidence_summary, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (hid, statement, result, confidence, json.dumps(evidence_summary), now)
        )
        row = conn.execute("SELECT * FROM hypotheses WHERE id = ?", (hid,)).fetchone()
    return row_dict(row)


# ─── Stats ──────────────────────────────────────────────────────────────────────

def get_stats():
    with connection() as conn:
        concepts = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
        relations = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        evidence = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
        hypotheses = conn.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0]
        categories = rows_dict(conn.execute(
            "SELECT category, COUNT(*) as count FROM concepts GROUP BY category ORDER BY count DESC"
        ).fetchall())
        return {
            "concepts": concepts,
            "relations": relations,
            "evidence": evidence,
            "hypotheses": hypotheses,
            "categories": categories,
        }