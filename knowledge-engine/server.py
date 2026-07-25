"""Local zero-dependency HTTP server for the Knowledge Engine."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
import json
import mimetypes
import traceback

import database
import graph
import knowledge
import reasoning
import search
import papers
import arxiv
import evidence
import paths
import fulltext

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
HOST = "127.0.0.1"
PORT = 8000


def json_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length > 1_000_000:
        raise ValueError("请求体过大")
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8") or "{}")


def clean_text(value, field, required=True, max_length=5000):
    value = str(value or "").strip()
    if required and not value:
        raise ValueError(f"{field}不能为空")
    if len(value) > max_length:
        raise ValueError(f"{field}长度不能超过{max_length}个字符")
    return value


def error_message(exc):
    if isinstance(exc, ValueError):
        return str(exc)
    if "UNIQUE constraint failed" in str(exc):
        return "名称已存在，请使用其他名称"
    if "FOREIGN KEY constraint failed" in str(exc):
        return "关联的概念不存在"
    return "服务器处理失败"


class Handler(BaseHTTPRequestHandler):
    server_version = "KnowledgeEngine/0.1"

    def log_message(self, fmt, *args):
        # Keep the terminal output useful without noisy browser asset logs.
        if not self.path.startswith("/static/"):
            super().log_message(fmt, *args)

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, content, content_type="text/plain; charset=utf-8", status=200):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path):
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if content_type.startswith("text/") or path.suffix in (".js", ".css"):
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        try:
            if path in ("/", "/index.html"):
                return self.send_file(STATIC_DIR / "index.html")
            if path.startswith("/static/"):
                safe_path = (STATIC_DIR / path.removeprefix("/static/")).resolve()
                if STATIC_DIR not in safe_path.parents:
                    return self.send_error(403)
                return self.send_file(safe_path)
            if path == "/api/stats":
                return self.send_json(knowledge.get_stats())
            if path == "/api/relations/types":
                return self.send_json({"types": knowledge.get_relation_types()})
            if path == "/api/concepts":
                q = (query.get("q") or [""])[0].strip()
                category = (query.get("category") or [""])[0].strip()
                if q:
                    results = search.search(q, top_k=50)
                else:
                    results = knowledge.list_concepts(category=category or None)
                return self.send_json({"items": results, "total": len(results)})
            if path == "/api/relations":
                cid = (query.get("concept_id") or [None])[0]
                return self.send_json({"items": knowledge.list_relations(cid)})
            if path == "/api/evidence":
                cid = (query.get("concept_id") or [None])[0]
                return self.send_json({"items": knowledge.list_evidence(cid)})
            if path == "/api/hypotheses":
                return self.send_json({"items": knowledge.list_hypotheses()})
            if path == "/api/graph":
                cid = (query.get("concept_id") or [None])[0]
                if cid:
                    svg, data = graph.render_svg(cid)
                else:
                    svg, data = graph.render_full_graph()
                return self.send_json({"svg": svg, "graph": data})
            if path.startswith("/api/concepts/"):
                cid = path.rsplit("/", 1)[-1]
                concept = knowledge.get_concept(cid)
                if not concept:
                    return self.send_json({"error": "概念不存在"}, 404)
                return self.send_json(concept)
            if path == "/api/papers":
                q = (query.get("q") or [""])[0].strip()
                return self.send_json({"items": papers.list_papers(q=q or None), "total": 0})
            if path == "/api/papers/fulltext":
                q = (query.get("q") or [""])[0].strip()
                if q:
                    return self.send_json({"items": fulltext.search(q), "total": 0})
                return self.send_json({"items": [], "total": 0})
            if path.startswith("/api/papers/"):
                cid = path.rsplit("/", 1)[-1]
                if path.endswith("/concepts"):
                    paper_id = path.split("/")[-2]
                    return self.send_json({"items": papers.get_paper_concepts(paper_id)})
                if path.endswith("/citations"):
                    paper_id = path.split("/")[-2]
                    return self.send_json(papers.get_citations(paper_id))
                paper = papers.get_paper(cid)
                if not paper:
                    return self.send_json({"error": "论文不存在"}, 404)
                return self.send_json(paper)
            if path == "/api/arxiv/search":
                q = (query.get("q") or [""])[0].strip()
                if not q:
                    return self.send_json({"items": [], "total": 0})
                return self.send_json(arxiv.search(q))
            if path == "/api/paths":
                hid = (query.get("hypothesis_id") or [None])[0]
                if hid:
                    return self.send_json({"items": paths.get_paths_for_hypothesis(hid)})
                return self.send_json({"items": [], "total": 0})
            return self.send_json({"error": "接口不存在"}, 404)
        except Exception as exc:
            traceback.print_exc()
            self.send_json({"error": error_message(exc)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            data = json_body(self)
            if path == "/api/concepts":
                name = clean_text(data.get("name"), "概念名称", max_length=100)
                description = clean_text(data.get("description"), "概念描述", max_length=5000)
                category = clean_text(data.get("category"), "分类", required=False, max_length=50) or "未分类"
                tags = data.get("tags") or []
                if not isinstance(tags, list):
                    raise ValueError("标签必须是数组")
                concept = knowledge.create_concept(name, description, category, tags[:20], clean_text(data.get("source"), "来源", False, 500))
                return self.send_json(concept, 201)
            if path == "/api/relations":
                source_id = clean_text(data.get("source_id"), "起点概念")
                target_id = clean_text(data.get("target_id"), "终点概念")
                if source_id == target_id:
                    raise ValueError("关系的两个概念不能相同")
                relation_type = clean_text(data.get("relation_type"), "关系类型", max_length=30)
                confidence = float(data.get("confidence", 0.5))
                if not 0 <= confidence <= 1:
                    raise ValueError("置信度必须在 0 到 1 之间")
                knowledge.create_relation(source_id, target_id, relation_type, clean_text(data.get("evidence"), "关系证据", False, 2000), confidence)
                return self.send_json({"items": knowledge.list_relations(source_id)}, 201)
            if path == "/api/evidence":
                concept_id = clean_text(data.get("concept_id"), "关联概念")
                content = clean_text(data.get("content"), "证据内容", max_length=5000)
                item = knowledge.create_evidence(concept_id, content, clean_text(data.get("source_url"), "来源链接", False, 1000), clean_text(data.get("source_title"), "来源标题", False, 300))
                return self.send_json(item, 201)
            if path == "/api/hypothesis":
                statement = clean_text(data.get("statement"), "假设内容", max_length=2000)
                return self.send_json(reasoning.verify(statement), 201)
            if path == "/api/hypothesis/analyze":
                statement = clean_text(data.get("statement"), "假设内容", max_length=2000)
                return self.send_json(evidence.analyze(statement), 201)
            if path == "/api/hypothesis/paths":
                statement = clean_text(data.get("statement"), "假设内容", max_length=2000)
                analysis = evidence.analyze(statement)
                hypothesis = reasoning.verify(statement)
                return self.send_json({"paths": paths.generate(analysis, hypothesis.get("id")), "hypothesis_id": hypothesis.get("id"), "analysis": analysis}, 201)
            if path == "/api/paths/select":
                path_id = clean_text(data.get("path_id"), "路径ID")
                note = clean_text(data.get("note", ""), "决策说明", required=False, max_length=1000)
                result = paths.select_path(path_id, note)
                if not result:
                    return self.send_json({"error": "路径不存在"}, 404)
                return self.send_json(result)
            if path == "/api/papers":
                title = clean_text(data.get("title"), "论文标题", max_length=500)
                authors = data.get("authors") or []
                if not isinstance(authors, list):
                    raise ValueError("authors 必须是数组")
                paper = papers.create_paper(
                    title, authors,
                    clean_text(data.get("venue", ""), "发表期刊", False, 200),
                    data.get("year"),
                    clean_text(data.get("doi", ""), "DOI", False, 200),
                    clean_text(data.get("arxiv_id", ""), "arXiv ID", False, 100),
                    clean_text(data.get("abstract", ""), "摘要", False, 10000),
                    "",
                    clean_text(data.get("url", ""), "链接", False, 500),
                )
                # Auto-link to concepts
                conc = knowledge.list_concepts(q=title, limit=5)
                for c in conc:
                    papers.link_paper_to_concept(paper["id"], c["id"], "related")
                return self.send_json(paper, 201)
            if path == "/api/papers/import-bibtex":
                bibtext = clean_text(data.get("bibtex"), "BibTeX 内容", max_length=50000)
                parsed = papers.parse_bibtex(bibtext)
                if not parsed:
                    raise ValueError("无法解析 BibTeX 内容")
                results = []
                for entry in parsed[:10]:
                    existing = papers.get_paper_by_doi(entry.get("doi", "")) if entry.get("doi") else None
                    if not existing and entry.get("arxiv_id"):
                        existing = papers.get_paper_by_arxiv(entry["arxiv_id"])
                    if existing:
                        results.append(existing)
                        continue
                    paper = papers.create_paper(
                        entry.get("title", ""), entry.get("authors", []),
                        entry.get("venue", ""), entry.get("year"),
                        entry.get("doi", ""), entry.get("arxiv_id", ""),
                        entry.get("abstract", ""), bibtext[:2000],
                        entry.get("url", ""),
                    )
                    conc = knowledge.list_concepts(q=paper["title"], limit=3)
                    for c in conc:
                        papers.link_paper_to_concept(paper["id"], c["id"], "related")
                    results.append(paper)
                return self.send_json({"items": results, "total": len(results)}, 201)
            if path == "/api/papers/import-doi":
                doi = clean_text(data.get("doi"), "DOI", max_length=200)
                existing = papers.get_paper_by_doi(doi)
                if existing:
                    return self.send_json(existing)
                meta = papers.resolve_doi(doi)
                if meta.get("error"):
                    raise ValueError(f"无法解析 DOI: {meta['error']}")
                paper = papers.create_paper(
                    meta.get("title", ""), meta.get("authors", []),
                    meta.get("venue", ""), meta.get("year"),
                    doi, "",
                    meta.get("abstract", ""), "", meta.get("url", ""),
                )
                conc = knowledge.list_concepts(q=paper["title"], limit=3)
                for c in conc:
                    papers.link_paper_to_concept(paper["id"], c["id"], "related")
                return self.send_json(paper, 201)
            if path == "/api/arxiv/import":
                arxiv_id = clean_text(data.get("arxiv_id"), "arXiv ID", max_length=50)
                existing = papers.get_paper_by_arxiv(arxiv_id)
                if existing:
                    return self.send_json(existing)
                entry = arxiv.fetch_by_id(arxiv_id)
                if not entry:
                    raise ValueError("arXiv 论文未找到")
                paper = papers.create_paper(
                    entry.get("title", ""), entry.get("authors", []),
                    entry.get("venue", ""), entry.get("year"),
                    entry.get("doi", ""), arxiv_id,
                    entry.get("abstract", ""), "", entry.get("url", ""),
                )
                conc = knowledge.list_concepts(q=paper["title"], limit=3)
                for c in conc:
                    papers.link_paper_to_concept(paper["id"], c["id"], "related")
                # Chunk abstract
                if entry.get("abstract"):
                    fulltext.chunk_paper(paper["id"], entry["abstract"], 500, 50)
                return self.send_json(paper, 201)
            return self.send_json({"error": "接口不存在"}, 404)
        except Exception as exc:
            traceback.print_exc()
            self.send_json({"error": error_message(exc)}, 400)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            data = json_body(self)
            if path.startswith("/api/concepts/"):
                cid = path.rsplit("/", 1)[-1]
                if not knowledge.get_concept(cid):
                    return self.send_json({"error": "概念不存在"}, 404)
                updates = {}
                for field in ("name", "description", "category", "source"):
                    if field in data:
                        updates[field] = clean_text(data[field], field, max_length=5000)
                if "tags" in data:
                    if not isinstance(data["tags"], list):
                        raise ValueError("标签必须是数组")
                    updates["tags"] = data["tags"][:20]
                return self.send_json(knowledge.update_concept(cid, **updates))
            return self.send_json({"error": "接口不存在"}, 404)
        except Exception as exc:
            self.send_json({"error": error_message(exc)}, 400)


def run(host=HOST, port=PORT):
    database.init_db()
    # Importing here avoids circular initialization while keeping server startup simple.
    from seed import seed
    seed()
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Knowledge Engine running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="人类知识与科学发现引擎")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    run(args.host, args.port)