"""SVG knowledge graph rendering."""
from database import connection
import json
import math


def _load_graph_data(concept_id):
    """Load concept + its relations for graph building."""
    with connection() as conn:
        concept = conn.execute(
            "SELECT id, name, category FROM concepts WHERE id = ?", (concept_id,)
        ).fetchone()
        if not concept:
            return None, []

        relations = conn.execute(
            """SELECT r.id, r.source_id, r.target_id, r.relation_type,
                      cs.name AS source_name, ct.name AS target_name
               FROM relations r
               JOIN concepts cs ON cs.id = r.source_id
               JOIN concepts ct ON ct.id = r.target_id
               WHERE r.source_id = ? OR r.target_id = ?""",
            (concept_id, concept_id)
        ).fetchall()

        # Collect neighbour IDs
        neighbour_ids = set()
        for r in relations:
            neighbour_ids.add(r["source_id"])
            neighbour_ids.add(r["target_id"])

        extra = []
        if neighbour_ids:
            placeholders = ",".join("?" for _ in neighbour_ids)
            extra = conn.execute(
                f"SELECT id, name, category FROM concepts WHERE id IN ({placeholders})",
                list(neighbour_ids)
            ).fetchall()

        return concept, relations, extra


def _layout_nodes(concept, extra, radius=160):
    """Simple circular layout: centre concept in middle, neighbours around."""
    nodes = []
    cx, cy = 300, 250

    # Centre node
    nodes.append({
        "id": concept["id"],
        "name": concept["name"],
        "category": concept["category"],
        "x": cx, "y": cy,
        "is_center": True,
    })

    neighbours = [e for e in extra if e["id"] != concept["id"]]
    n = len(neighbours)
    for i, nb in enumerate(neighbours):
        angle = 2 * math.pi * i / n - math.pi / 2
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        nodes.append({
            "id": nb["id"],
            "name": nb["name"],
            "category": nb["category"],
            "x": round(x, 1), "y": round(y, 1),
            "is_center": False,
        })

    return nodes


def _color_for_category(cat):
    palette = {
        "人工智能": "#6366f1",
        "计算机科学": "#3b82f6",
        "生物学": "#10b981",
        "物理学": "#f59e0b",
        "化学": "#ef4444",
        "天文学": "#8b5cf6",
        "数学": "#ec4899",
        "工程学": "#14b8a6",
        "哲学": "#f97316",
        "未分类": "#6b7280",
    }
    return palette.get(cat, "#6b7280")


def render_svg(concept_id, width=600, height=500):
    """Return an SVG string and JSON graph data for the given concept."""
    concept, relations, extra = _load_graph_data(concept_id)
    if not concept:
        return None, {"error": "Concept not found"}

    nodes = _layout_nodes(concept, extra)

    # Build node map
    node_map = {n["id"]: n for n in nodes}

    # Collect edges
    edges = []
    for r in relations:
        src = node_map.get(r["source_id"])
        tgt = node_map.get(r["target_id"])
        if src and tgt:
            edges.append({
                "id": r["id"],
                "source": src,
                "target": tgt,
                "type": r["relation_type"],
            })

    # Generate SVG
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" style="background:#f8fafc;border-radius:8px;font-family:sans-serif;">',
        '<defs>',
        '  <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">',
        '    <polygon points="0 0, 10 3.5, 0 7" fill="#94a3b8" />',
        '  </marker>',
        '</defs>',
    ]

    # Edges
    for edge in edges:
        sx, sy = edge["source"]["x"], edge["source"]["y"]
        tx, ty = edge["target"]["x"], edge["target"]["y"]
        # Shorten line to stop at node edge
        dx, dy = tx - sx, ty - sy
        dist = math.hypot(dx, dy)
        if dist < 1:
            continue
        r = 25
        sx2 = sx + dx * r / dist
        sy2 = sy + dy * r / dist
        tx2 = tx - dx * r / dist
        ty2 = ty - dy * r / dist
        svg_parts.append(
            f'<line x1="{sx2:.1f}" y1="{sy2:.1f}" x2="{tx2:.1f}" y2="{ty2:.1f}" '
            f'stroke="#94a3b8" stroke-width="1.5" marker-end="url(#arrowhead)" />'
        )
        # Relation label at midpoint
        mx = (sx + tx) / 2
        my = (sy + ty) / 2 - 8
        svg_parts.append(
            f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" '
            f'fill="#64748b" font-size="10" font-family="sans-serif">{edge["type"]}</text>'
        )

    # Nodes
    for node in nodes:
        color = _color_for_category(node["category"])
        r = 28 if node["is_center"] else 22
        svg_parts.append(
            f'<rect x="{node["x"] - r}" y="{node["y"] - 10}" width="{r * 2}" height="20" rx="10" '
            f'fill="{color}" opacity="0.9" />'
        )
        svg_parts.append(
            f'<text x="{node["x"]}" y="{node["y"] + 4}" text-anchor="middle" '
            f'fill="white" font-size="11" font-weight="600" font-family="sans-serif">'
            f'{node["name"]}</text>'
        )

    svg_parts.append("</svg>")
    svg = "\n".join(svg_parts)

    graph_data = {
        "nodes": nodes,
        "edges": edges,
    }
    return svg, graph_data


def render_full_graph(max_nodes=30, width=700, height=550):
    """Render a graph of the most connected concepts."""
    with connection() as conn:
        rows = conn.execute(
            """SELECT c.id, c.name, c.category,
                      (SELECT COUNT(*) FROM relations WHERE source_id = c.id OR target_id = c.id) AS degree
               FROM concepts c ORDER BY degree DESC LIMIT ?""",
            (max_nodes,)
        ).fetchall()

    if not rows:
        return None, {"error": "No concepts"}

    nodes = []
    n = len(rows)
    cx, cy = width / 2, height / 2
    max_radius = min(cx, cy) - 40
    for i, row in enumerate(rows):
        angle = 2 * math.pi * i / n - math.pi / 2
        r = 30 + (max_radius - 30) * (row["degree"] / max(row["degree"], 1)) ** 0.5
        nodes.append({
            "id": row["id"],
            "name": row["name"],
            "category": row["category"],
            "x": round(cx + r * math.cos(angle), 1),
            "y": round(cy + r * math.sin(angle), 1),
            "degree": row["degree"],
        })

    node_map = {n["id"]: n for n in nodes}

    with connection() as conn:
        rels = conn.execute(
            "SELECT source_id, target_id, relation_type FROM relations"
        ).fetchall()

    edges = []
    for r in rels:
        src = node_map.get(r["source_id"])
        tgt = node_map.get(r["target_id"])
        if src and tgt:
            edges.append({"source": src, "target": tgt, "type": r["relation_type"]})

    # SVG
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" style="background:#f8fafc;border-radius:8px;font-family:sans-serif;">',
        '<defs>',
        '  <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">',
        '    <polygon points="0 0, 10 3.5, 0 7" fill="#94a3b8" />',
        '  </marker>',
        '</defs>',
    ]

    for edge in edges:
        sx, sy = edge["source"]["x"], edge["source"]["y"]
        tx, ty = edge["target"]["x"], edge["target"]["y"]
        dx, dy = tx - sx, ty - sy
        dist = math.hypot(dx, dy)
        if dist < 1:
            continue
        r = 20
        sx2 = sx + dx * r / dist
        sy2 = sy + dy * r / dist
        tx2 = tx - dx * r / dist
        ty2 = ty - dy * r / dist
        svg_parts.append(
            f'<line x1="{sx2:.1f}" y1="{sy2:.1f}" x2="{tx2:.1f}" y2="{ty2:.1f}" '
            f'stroke="#cbd5e1" stroke-width="1" marker-end="url(#arrowhead)" />'
        )

    for node in nodes:
        color = _color_for_category(node["category"])
        svg_parts.append(
            f'<rect x="{node["x"] - 20}" y="{node["y"] - 8}" width="40" height="16" rx="8" '
            f'fill="{color}" opacity="0.85" />'
        )
        svg_parts.append(
            f'<text x="{node["x"]}" y="{node["y"] + 3}" text-anchor="middle" '
            f'fill="white" font-size="9" font-weight="600">{node["name"]}</text>'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts), {"nodes": nodes, "edges": edges}