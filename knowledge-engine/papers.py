"""Paper metadata, BibTeX/DOI parsing, CRUD, and citation network."""
import json
import re
import urllib.request
import urllib.parse
from database import connection, row_dict, rows_dict, new_id, now_iso

# ─── BibTeX parser ──────────────────────────────────────────────────────────────

def _clean_bibtex_value(raw):
    """Strip braces, quotes, and whitespace from a BibTeX field value."""
    raw = raw.strip()
    if raw.startswith("{") and raw.endswith("}"):
        raw = raw[1:-1]
    elif raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    return raw.strip()


def parse_bibtex(text):
    """Parse BibTeX text into a list of paper dicts. Returns list (usually 1 item)."""
    entries = []
    for match in re.finditer(r"@(\w+)\s*\{\s*([^,]+)\s*,", text, re.DOTALL):
        entry_type, cite_key = match.group(1), match.group(2)
        start = match.end()
        depth = 1
        i = start
        in_quote = False
        while i < len(text):
            char = text[i]
            if char == '"' and (i == 0 or text[i - 1] != "\\"):
                in_quote = not in_quote
            elif not in_quote:
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        break
            i += 1
        entries.append((entry_type, cite_key, text[start:i]))
    papers = []
    for entry_type, cite_key, fields_raw in entries:
        paper = {"entry_type": entry_type.lower(), "cite_key": cite_key.strip(), "import_errors": []}
        # Extract fields
        field_re = r"(\w+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|\"(?:[^\"\\]|\\.)*\"|[^,\n]+)"
        for match in re.finditer(field_re, fields_raw):
            key = match.group(1).lower()
            val = _clean_bibtex_value(match.group(2))
            if key == "title":
                paper["title"] = val
            elif key == "author":
                paper["authors"] = [a.strip() for a in val.replace("\n", " ").split(" and ")]
            elif key == "journal":
                paper["venue"] = val
            elif key == "booktitle":
                if "venue" not in paper:
                    paper["venue"] = val
            elif key == "year":
                paper["year"] = _parse_year(val)
            elif key == "doi":
                paper["doi"] = val.lower()
            elif key == "url":
                paper["url"] = val
            elif key == "abstract":
                paper["abstract"] = val
            elif key == "archiveprefix" and val.lower() == "arxiv":
                pass  # eprint field holds the arxiv ID
            elif key == "eprint":
                paper["arxiv_id"] = val
        # Set defaults
        paper.setdefault("title", "")
        paper.setdefault("authors", [])
        paper.setdefault("venue", "")
        paper.setdefault("year", None)
        paper.setdefault("doi", "")
        paper.setdefault("arxiv_id", "")
        paper.setdefault("abstract", "")
        paper.setdefault("url", "")
        papers.append(paper)
    return papers


def _parse_year(val):
    try:
        return int(val.strip("{} "))
    except (ValueError, TypeError):
        return None


# ─── DOI resolver (via crossref.org) ────────────────────────────────────────────

def resolve_doi(doi):
    """Fetch paper metadata from Crossref by DOI. Returns dict or None."""
    doi = doi.strip().lower()
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Atlas/0.1 (local knowledge engine)"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        msg = data.get("message", {})
        paper = {
            "title": (msg.get("title") or [""])[0],
            "authors": [a.get("given", "") + " " + a.get("family", "") for a in msg.get("author", [])],
            "venue": (msg.get("container-title") or [""])[0] if msg.get("container-title") else (msg.get("publisher") or ""),
            "year": (msg.get("published-print") or msg.get("published-online") or msg.get("issued") or {}).get("date-parts", [[None]])[0][0],
            "doi": doi,
            "url": f"https://doi.org/{doi}",
            "abstract": msg.get("abstract", "").replace("<jats:p>", "").replace("</jats:p>", "") if msg.get("abstract") else "",
        }
        return paper
    except Exception as exc:
        return {"error": str(exc)}


# ─── CRUD ───────────────────────────────────────────────────────────────────────

def list_papers(q=None, limit=50, offset=0):
    with connection() as conn:
        if q:
            like = f"%{q}%"
            return rows_dict(conn.execute(
                """SELECT * FROM papers WHERE title LIKE ? OR authors LIKE ? OR abstract LIKE ?
                   ORDER BY year DESC, added_at DESC LIMIT ? OFFSET ?""",
                (like, like, like, limit, offset)
            ).fetchall())
        return rows_dict(conn.execute(
            "SELECT * FROM papers ORDER BY year DESC, added_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall())


def get_paper(paper_id):
    with connection() as conn:
        return row_dict(conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone())


def get_paper_by_doi(doi):
    with connection() as conn:
        return row_dict(conn.execute("SELECT * FROM papers WHERE doi = ?", (doi,)).fetchone())


def get_paper_by_arxiv(arxiv_id):
    with connection() as conn:
        return row_dict(conn.execute("SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,)).fetchone())


def create_paper(title, authors=None, venue="", year=None, doi="", arxiv_id="", abstract="", bibtex="", url=""):
    now = now_iso()
    pid = new_id()
    with connection() as conn:
        conn.execute(
            """INSERT INTO papers (id, title, authors, venue, year, doi, arxiv_id, abstract, bibtex, url, added_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, title, json.dumps(authors or []), venue, year, doi, arxiv_id, abstract, bibtex, url, now)
        )
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (pid,)).fetchone()
    return row_dict(row)


def update_paper(paper_id, **kwargs):
    allowed = {"title", "authors", "venue", "year", "doi", "arxiv_id", "abstract", "bibtex", "url"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_paper(paper_id)
    if "authors" in updates and isinstance(updates["authors"], list):
        updates["authors"] = json.dumps(updates["authors"])
    cols = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [paper_id]
    with connection() as conn:
        conn.execute(f"UPDATE papers SET {cols} WHERE id = ?", vals)
    return get_paper(paper_id)


def delete_paper(paper_id):
    with connection() as conn:
        conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))


# ─── Paper-Concept links ────────────────────────────────────────────────────────

def link_paper_to_concept(paper_id, concept_id, relevance="related"):
    with connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO paper_concepts (paper_id, concept_id, relevance) VALUES (?, ?, ?)",
            (paper_id, concept_id, relevance)
        )


def get_paper_concepts(paper_id):
    with connection() as conn:
        return rows_dict(conn.execute(
            """SELECT c.*, pc.relevance FROM paper_concepts pc
               JOIN concepts c ON c.id = pc.concept_id
               WHERE pc.paper_id = ? ORDER BY pc.relevance""",
            (paper_id,)
        ).fetchall())


def get_concept_papers(concept_id):
    with connection() as conn:
        return rows_dict(conn.execute(
            """SELECT p.*, pc.relevance FROM paper_concepts pc
               JOIN papers p ON p.id = pc.paper_id
               WHERE pc.concept_id = ? ORDER BY p.year DESC""",
            (concept_id,)
        ).fetchall())


# ─── Citations ──────────────────────────────────────────────────────────────────

def create_citation(citing_id, cited_id, context=""):
    now = now_iso()
    cid = new_id()
    with connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO paper_citations (id, citing_id, cited_id, context, created_at) VALUES (?, ?, ?, ?, ?)",
            (cid, citing_id, cited_id, context, now)
        )


def get_citations(paper_id):
    """Get both citing and cited for a paper."""
    with connection() as conn:
        citing = rows_dict(conn.execute(
            """SELECT pc.*, p.title AS citing_title, p.authors AS citing_authors, p.year AS citing_year
               FROM paper_citations pc JOIN papers p ON p.id = pc.citing_id
               WHERE pc.cited_id = ?""",
            (paper_id,)
        ).fetchall())
        cited = rows_dict(conn.execute(
            """SELECT pc.*, p.title AS cited_title, p.authors AS cited_authors, p.year AS cited_year
               FROM paper_citations pc JOIN papers p ON p.id = pc.cited_id
               WHERE pc.citing_id = ?""",
            (paper_id,)
        ).fetchall())
        return {"citing": citing, "cited": cited}


# ─── Full-text chunks ───────────────────────────────────────────────────────────

def add_chunk(paper_id, chunk_index, content):
    now = now_iso()
    cid = new_id()
    with connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO paper_chunks (id, paper_id, chunk_index, content, added_at) VALUES (?, ?, ?, ?, ?)",
            (cid, paper_id, chunk_index, content, now)
        )


def get_chunks(paper_id):
    with connection() as conn:
        return rows_dict(conn.execute(
            "SELECT * FROM paper_chunks WHERE paper_id = ? ORDER BY chunk_index", (paper_id,)
        ).fetchall())


def search_chunks(query, limit=20):
    """Simple keyword search over paper chunks."""
    with connection() as conn:
        like = f"%{query}%"
        return rows_dict(conn.execute(
            """SELECT pc.*, p.title AS paper_title, p.authors AS paper_authors
               FROM paper_chunks pc JOIN papers p ON p.id = pc.paper_id
               WHERE pc.content LIKE ?
               ORDER BY pc.chunk_index LIMIT ?""",
            (like, limit)
        ).fetchall())