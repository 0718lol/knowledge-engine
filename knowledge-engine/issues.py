"""Curated research issues, claims, and claim-level evidence."""
import re

from database import connection, row_dict, rows_dict


def list_issues():
    with connection() as conn:
        return rows_dict(conn.execute(
            """SELECT i.*,
                      (SELECT COUNT(*) FROM claims c WHERE c.issue_id = i.id) AS claim_count,
                      (SELECT COUNT(*) FROM issue_concepts ic WHERE ic.issue_id = i.id) AS concept_count
               FROM issues i ORDER BY i.updated_at DESC"""
        ).fetchall())


def get_issue(issue_id):
    with connection() as conn:
        issue = row_dict(conn.execute("SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone())
        if not issue:
            return None
        issue["concepts"] = rows_dict(conn.execute(
            """SELECT c.id, c.name, c.category, ic.role
               FROM issue_concepts ic JOIN concepts c ON c.id = ic.concept_id
               WHERE ic.issue_id = ? ORDER BY ic.sort_order, c.name""",
            (issue_id,),
        ).fetchall())
        claim_rows = conn.execute(
            "SELECT * FROM claims WHERE issue_id = ? ORDER BY sort_order, created_at", (issue_id,)
        ).fetchall()
        issue["claims"] = []
        for claim_row in claim_rows:
            claim = row_dict(claim_row)
            claim["evidence"] = rows_dict(conn.execute(
                """SELECT ce.*, p.title AS paper_title, p.year AS paper_year
                   FROM claim_evidence ce LEFT JOIN papers p ON p.id = ce.paper_id
                   WHERE ce.claim_id = ? ORDER BY ce.sort_order, ce.created_at""",
                (claim["id"],),
            ).fetchall())
            issue["claims"].append(claim)
        return issue


def match_claims(statement, limit=3):
    """Return curated claims close enough to provide research context, not a verdict."""
    query_units = _units(statement)
    if not query_units:
        return []
    with connection() as conn:
        rows = conn.execute(
            """SELECT c.id, c.statement, c.position, c.assessment, c.confidence, c.keywords,
                      i.id AS issue_id, i.title AS issue_title
               FROM claims c JOIN issues i ON i.id = c.issue_id"""
        ).fetchall()
    matches = []
    for row in rows:
        item = row_dict(row)
        target = " ".join([item["statement"], item["issue_title"], *item.get("keywords", [])])
        target_units = _units(target)
        overlap = query_units & target_units
        score = 2 * len(overlap) / max(1, len(query_units) + len(target_units))
        keyword_hits = sum(1 for keyword in item.get("keywords", []) if keyword.lower() in statement.lower())
        score = min(1.0, score + min(.36, keyword_hits * .12))
        if score >= .16 or keyword_hits >= 2:
            item["match_score"] = round(score, 3)
            matches.append(item)
    matches.sort(key=lambda item: (item["match_score"], item["confidence"]), reverse=True)
    return matches[:limit]


def _units(text):
    normalized = re.sub(r"\s+", "", str(text or "").lower())
    cjk = "".join(re.findall(r"[\u3400-\u9fff]", normalized))
    units = {cjk[index:index + 2] for index in range(max(0, len(cjk) - 1))}
    units.update(re.findall(r"[a-z0-9]{2,}", normalized))
    return units
