"""SQLite persistence for the local knowledge graph."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import uuid

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "knowledge.db"
SCHEMA_VERSION = 6


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id():
    return uuid.uuid4().hex


@contextmanager
def connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS concepts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '未分类',
                tags TEXT NOT NULL DEFAULT '[]',
                source TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS relations (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                target_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                relation_type TEXT NOT NULL,
                evidence TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                UNIQUE(source_id, target_id, relation_type)
            );
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT '',
                source_title TEXT NOT NULL DEFAULT '',
                added_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS hypotheses (
                id TEXT PRIMARY KEY,
                statement TEXT NOT NULL,
                result TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0,
                evidence_summary TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_concepts_category ON concepts(category);
            CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
            CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
            CREATE INDEX IF NOT EXISTS idx_evidence_concept ON evidence(concept_id);
            CREATE TABLE IF NOT EXISTS concept_sections (
                id TEXT PRIMARY KEY,
                concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                section_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(concept_id, section_type, title)
            );
            CREATE INDEX IF NOT EXISTS idx_concept_sections_concept
                ON concept_sections(concept_id, sort_order);
            CREATE TABLE IF NOT EXISTS issues (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL UNIQUE,
                question TEXT NOT NULL,
                summary TEXT NOT NULL,
                current_assessment TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS issue_concepts (
                issue_id TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
                concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                role TEXT NOT NULL DEFAULT 'related',
                sort_order INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (issue_id, concept_id)
            );
            CREATE TABLE IF NOT EXISTS claims (
                id TEXT PRIMARY KEY,
                issue_id TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
                statement TEXT NOT NULL,
                position TEXT NOT NULL,
                assessment TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                keywords TEXT NOT NULL DEFAULT '[]',
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(issue_id, statement)
            );
            CREATE TABLE IF NOT EXISTS claim_evidence (
                id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
                stance TEXT NOT NULL,
                summary TEXT NOT NULL,
                strength TEXT NOT NULL DEFAULT 'context',
                source_title TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                paper_id TEXT REFERENCES papers(id) ON DELETE SET NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(claim_id, stance, source_title, summary)
            );
            CREATE INDEX IF NOT EXISTS idx_claims_issue ON claims(issue_id, sort_order);
            CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim ON claim_evidence(claim_id, sort_order);
            CREATE TABLE IF NOT EXISTS papers (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                authors TEXT NOT NULL DEFAULT '[]',
                venue TEXT NOT NULL DEFAULT '',
                year INTEGER,
                doi TEXT NOT NULL DEFAULT '',
                arxiv_id TEXT NOT NULL DEFAULT '',
                abstract TEXT NOT NULL DEFAULT '',
                bibtex TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                added_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi) WHERE doi != '';
            CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_arxiv_id ON papers(arxiv_id) WHERE arxiv_id != '';
            CREATE INDEX IF NOT EXISTS idx_papers_title ON papers(title);
            CREATE TABLE IF NOT EXISTS paper_concepts (
                paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                relevance TEXT NOT NULL DEFAULT 'related',
                PRIMARY KEY (paper_id, concept_id)
            );
            CREATE TABLE IF NOT EXISTS paper_citations (
                id TEXT PRIMARY KEY,
                citing_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                cited_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                context TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(citing_id, cited_id)
            );
            CREATE TABLE IF NOT EXISTS paper_chunks (
                id TEXT PRIMARY KEY,
                paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                added_at TEXT NOT NULL,
                UNIQUE(paper_id, chunk_index)
            );
            CREATE TABLE IF NOT EXISTS research_paths (
                id TEXT PRIMARY KEY,
                hypothesis_id TEXT REFERENCES hypotheses(id) ON DELETE SET NULL,
                path_label TEXT NOT NULL,
                description TEXT NOT NULL,
                concepts TEXT NOT NULL DEFAULT '[]',
                papers TEXT NOT NULL DEFAULT '[]',
                is_selected INTEGER NOT NULL DEFAULT 0,
                decision_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_paper_concepts_concept ON paper_concepts(concept_id);
            CREATE INDEX IF NOT EXISTS idx_citations_citing ON paper_citations(citing_id);
            CREATE INDEX IF NOT EXISTS idx_citations_cited ON paper_citations(cited_id);
            CREATE INDEX IF NOT EXISTS idx_paper_chunks_paper ON paper_chunks(paper_id);
            CREATE INDEX IF NOT EXISTS idx_paths_hypothesis ON research_paths(hypothesis_id);
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY,
                agent_type TEXT NOT NULL,
                question TEXT NOT NULL,
                context TEXT NOT NULL DEFAULT '{}',
                result TEXT NOT NULL DEFAULT '{}',
                model TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_agent_runs_created
                ON agent_runs(created_at);
            """
        )
        _run_migrations(conn)


def _run_migrations(conn):
    row = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
    version = int(row[0]) if row else 0

    if version < 1:
        conn.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS relations_validate_insert
            BEFORE INSERT ON relations
            BEGIN
                SELECT CASE WHEN NEW.source_id = NEW.target_id
                    THEN RAISE(ABORT, 'relation endpoints must differ') END;
                SELECT CASE WHEN NEW.confidence < 0 OR NEW.confidence > 1
                    THEN RAISE(ABORT, 'relation confidence out of range') END;
            END;
            CREATE TRIGGER IF NOT EXISTS relations_validate_update
            BEFORE UPDATE ON relations
            BEGIN
                SELECT CASE WHEN NEW.source_id = NEW.target_id
                    THEN RAISE(ABORT, 'relation endpoints must differ') END;
                SELECT CASE WHEN NEW.confidence < 0 OR NEW.confidence > 1
                    THEN RAISE(ABORT, 'relation confidence out of range') END;
            END;
            """
        )
        version = 1

    if version < 2:
        _repair_seed_relations(conn)
        version = 2

    if version < 3:
        _rebuild_abstract_chunks(conn)
        version = 3

    if version < 4:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS concept_sections (
                id TEXT PRIMARY KEY,
                concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                section_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(concept_id, section_type, title)
            );
            CREATE INDEX IF NOT EXISTS idx_concept_sections_concept
                ON concept_sections(concept_id, sort_order);
            """
        )
        version = 4

    if version < 5:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS issues (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL UNIQUE,
                question TEXT NOT NULL,
                summary TEXT NOT NULL,
                current_assessment TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS issue_concepts (
                issue_id TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
                concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                role TEXT NOT NULL DEFAULT 'related',
                sort_order INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (issue_id, concept_id)
            );
            CREATE TABLE IF NOT EXISTS claims (
                id TEXT PRIMARY KEY,
                issue_id TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
                statement TEXT NOT NULL,
                position TEXT NOT NULL,
                assessment TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                keywords TEXT NOT NULL DEFAULT '[]',
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(issue_id, statement)
            );
            CREATE TABLE IF NOT EXISTS claim_evidence (
                id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
                stance TEXT NOT NULL,
                summary TEXT NOT NULL,
                strength TEXT NOT NULL DEFAULT 'context',
                source_title TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                paper_id TEXT REFERENCES papers(id) ON DELETE SET NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(claim_id, stance, source_title, summary)
            );
            CREATE INDEX IF NOT EXISTS idx_claims_issue ON claims(issue_id, sort_order);
            CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim ON claim_evidence(claim_id, sort_order);
            """
        )
        version = 5

    if version < 6:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY,
                agent_type TEXT NOT NULL,
                question TEXT NOT NULL,
                context TEXT NOT NULL DEFAULT '{}',
                result TEXT NOT NULL DEFAULT '{}',
                model TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_agent_runs_created
                ON agent_runs(created_at);
            """
        )
        version = 6

    conn.execute(
        """INSERT INTO schema_meta(key, value) VALUES ('schema_version', ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
        (str(version),),
    )


def _repair_seed_relations(conn):
    """Repair known semantic errors from the original bundled seed data."""
    names = (
        "机器学习", "深度学习", "人工智能伦理", "细胞", "DNA", "强化学习",
        "数据库", "进化论", "大爆炸理论", "相对论", "操作系统", "TCP/IP协议",
    )
    ids = {
        row["name"]: row["id"]
        for row in conn.execute(
            f"SELECT id, name FROM concepts WHERE name IN ({','.join('?' for _ in names)})",
            names,
        ).fetchall()
    }

    ethics = ids.get("人工智能伦理")
    if ethics:
        conn.execute("DELETE FROM relations WHERE source_id = ? AND target_id = ?", (ethics, ethics))

    repairs = [
        ("机器学习", "深度学习", "is_a", "深度学习", "机器学习", "is_a"),
        ("机器学习", "数据库", "supports", "数据库", "机器学习", "supports"),
        ("进化论", "DNA", "supports", "DNA", "进化论", "supports"),
        ("细胞", "DNA", "part_of", "DNA", "细胞", "part_of"),
        ("大爆炸理论", "相对论", "supports", "大爆炸理论", "相对论", "depends_on"),
        ("深度学习", "强化学习", "is_a", "深度学习", "强化学习", "related_to"),
        ("操作系统", "TCP/IP协议", "depends_on", "操作系统", "TCP/IP协议", "related_to"),
    ]
    for old_source, old_target, old_type, new_source, new_target, new_type in repairs:
        old_sid, old_tid = ids.get(old_source), ids.get(old_target)
        new_sid, new_tid = ids.get(new_source), ids.get(new_target)
        if not all((old_sid, old_tid, new_sid, new_tid)):
            continue
        row = conn.execute(
            """SELECT id FROM relations
               WHERE source_id = ? AND target_id = ? AND relation_type = ?""",
            (old_sid, old_tid, old_type),
        ).fetchone()
        if not row:
            continue
        duplicate = conn.execute(
            """SELECT id FROM relations
               WHERE source_id = ? AND target_id = ? AND relation_type = ? AND id != ?""",
            (new_sid, new_tid, new_type, row["id"]),
        ).fetchone()
        if duplicate:
            conn.execute("DELETE FROM relations WHERE id = ?", (row["id"],))
        else:
            conn.execute(
                "UPDATE relations SET source_id = ?, target_id = ?, relation_type = ? WHERE id = ?",
                (new_sid, new_tid, new_type, row["id"]),
            )


def _rebuild_abstract_chunks(conn, chunk_size=500, overlap=50):
    """Rebuild legacy token-joined chunks while preserving original prose."""
    papers = conn.execute("SELECT id, abstract FROM papers WHERE abstract != ''").fetchall()
    for paper in papers:
        conn.execute("DELETE FROM paper_chunks WHERE paper_id = ?", (paper["id"],))
        text = paper["abstract"].strip()
        step = chunk_size - overlap
        for index, start in enumerate(range(0, len(text), step)):
            content = text[start:start + chunk_size].strip()
            if content:
                conn.execute(
                    """INSERT INTO paper_chunks(id, paper_id, chunk_index, content, added_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (new_id(), paper["id"], index, content, now_iso()),
                )
            if start + chunk_size >= len(text):
                break


def row_dict(row):
    if row is None:
        return None
    item = dict(row)
    for key in ("tags", "evidence_summary", "authors", "concepts", "papers", "keywords"):
        if key in item:
            try:
                item[key] = json.loads(item[key])
            except (TypeError, ValueError):
                item[key] = []
    return item


def rows_dict(rows):
    return [row_dict(row) for row in rows]
