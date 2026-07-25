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