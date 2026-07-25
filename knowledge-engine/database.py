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
            """
        )


def row_dict(row):
    if row is None:
        return None
    item = dict(row)
    for key in ("tags", "evidence_summary", "authors", "concepts", "papers"):
        if key in item:
            try:
                item[key] = json.loads(item[key])
            except (TypeError, ValueError):
                item[key] = []
    return item


def rows_dict(rows):
    return [row_dict(row) for row in rows]
