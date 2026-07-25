"""arXiv API search and import (zero external dependencies, uses urllib + xml.etree)."""
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re

ARXIV_SEARCH_URL = "http://export.arxiv.org/api/query"
ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def search(query, max_results=10, sort_by="relevance"):
    """Search arXiv via the public API. Returns list of paper dicts."""
    params = {
        "search_query": f"all:{query}",
        "max_results": str(max_results),
        "sortBy": sort_by,
    }
    url = f"{ARXIV_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Atlas/0.1 (local knowledge engine)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
        root = ET.fromstring(raw)
    except Exception as exc:
        return {"error": str(exc), "items": []}

    items = []
    for entry in root.findall("atom:entry", ARXIV_NS):
        paper = _parse_entry(entry)
        if paper:
            items.append(paper)
    return {"items": items, "total": len(items)}


def fetch_by_id(arxiv_id):
    """Fetch a single paper by arXiv ID. Returns paper dict or None."""
    arxiv_id = re.sub(r"^arxiv:", "", arxiv_id, flags=re.IGNORECASE).strip()
    url = f"{ARXIV_SEARCH_URL}?id_list={urllib.parse.quote(arxiv_id)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Atlas/0.1 (local knowledge engine)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
        root = ET.fromstring(raw)
        entry = root.find("atom:entry", ARXIV_NS)
        if entry is not None:
            return _parse_entry(entry)
    except Exception:
        pass
    return None


def _parse_entry(entry):
    """Parse a single Atom entry into a paper dict."""
    try:
        title = (entry.find("atom:title", ARXIV_NS).text or "").strip().replace("\n", " ").replace("  ", " ")
        summary = (entry.find("atom:summary", ARXIV_NS).text or "").strip().replace("\n", " ").replace("  ", " ")

        authors = []
        for author_el in entry.findall("atom:author", ARXIV_NS):
            name = (author_el.find("atom:name", ARXIV_NS).text or "").strip()
            if name:
                authors.append(name)

        # Get arXiv ID from the link
        arxiv_id = ""
        for link in entry.findall("atom:link", ARXIV_NS):
            href = (link.get("href") or "")
            m = re.search(r"arxiv\.org/abs/(\d+\.\d+)", href)
            if m:
                arxiv_id = m.group(1)
                break
            m2 = re.search(r"arxiv\.org/abs/(\w+/\d+)", href)
            if m2:
                arxiv_id = m2.group(1)

        # Get DOI from arxiv:doi if present
        doi = ""
        doi_el = entry.find("arxiv:doi", ARXIV_NS)
        if doi_el is not None and doi_el.text:
            doi = doi_el.text.strip()

        # Get published date
        published = entry.find("atom:published", ARXIV_NS)
        year = None
        if published is not None and published.text:
            m = re.match(r"(\d{4})", published.text)
            if m:
                year = int(m.group(1))

        # Categories
        categories = []
        for cat in entry.findall("atom:category", ARXIV_NS):
            term = cat.get("term", "")
            if term:
                categories.append(term)

        return {
            "title": title,
            "authors": authors,
            "abstract": summary,
            "arxiv_id": arxiv_id,
            "doi": doi,
            "year": year,
            "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
            "venue": f"arXiv ({', '.join(categories[:3])})" if categories else "arXiv",
            "categories": categories,
        }
    except Exception:
        return None