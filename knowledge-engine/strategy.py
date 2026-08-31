"""Technical strategy projects and agent orchestration."""
import json

import database
import strategy_agent


def _context(question, limit=16):
    tokens = [part.strip() for part in question.replace("?", " ").replace("？", " ").split() if part.strip()]
    like = "%" + (tokens[0] if tokens else question[:40]) + "%"
    with database.connection() as conn:
        concepts = database.rows_dict(conn.execute(
            """SELECT id, name, description, category, tags, source FROM concepts
               WHERE name LIKE ? OR description LIKE ? OR category LIKE ?
               ORDER BY updated_at DESC LIMIT ?""",
            (like, like, like, limit),
        ).fetchall())
        papers = database.rows_dict(conn.execute(
            """SELECT id, title, authors, venue, year, abstract, url FROM papers
               WHERE title LIKE ? OR abstract LIKE ? ORDER BY added_at DESC LIMIT ?""",
            (like, like, min(limit, 8)),
        ).fetchall())
        issues = database.rows_dict(conn.execute(
            """SELECT id, title, question, summary, current_assessment, status
               FROM issues WHERE title LIKE ? OR question LIKE ? LIMIT ?""",
            (like, like, min(limit, 6)),
        ).fetchall())
    return {"concepts": concepts, "papers": papers, "issues": issues}


def analyze(question):
    question = str(question or "").strip()
    if not question:
        raise ValueError("技术决策问题不能为空")
    if len(question) > 2000:
        raise ValueError("技术决策问题长度不能超过 2000 个字符")
    context = _context(question)
    result = strategy_agent.analyze(question, context)
    with database.connection() as conn:
        run_id = database.new_id()
        conn.execute(
            """INSERT INTO agent_runs
               (id, agent_type, question, context, result, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (run_id, "technical_strategy", question, json.dumps(context, ensure_ascii=False),
             json.dumps(result, ensure_ascii=False), strategy_agent.DEFAULT_MODEL, database.now_iso()),
        )
    result["run_id"] = run_id
    result["context"] = context
    return result


def list_runs(limit=20):
    with database.connection() as conn:
        rows = database.rows_dict(conn.execute(
            """SELECT id, agent_type, question, result, model, created_at
               FROM agent_runs ORDER BY created_at DESC LIMIT ?""", (limit,)
        ).fetchall())
    for row in rows:
        if isinstance(row.get("result"), str):
            try:
                row["result"] = json.loads(row["result"])
            except json.JSONDecodeError:
                row["result"] = {}
    return rows
