import graph
import knowledge

from tests.support import DatabaseTestCase


class GraphRenderingTests(DatabaseTestCase):
    def test_node_boxes_expand_for_long_labels(self):
        short = knowledge.create_concept("AI", "short")
        long = knowledge.create_concept("自然语言处理", "long")
        knowledge.create_relation(short["id"], long["id"], "related_to")

        _, data = graph.render_svg(short["id"])
        widths = {node["name"]: node["width"] for node in data["nodes"]}

        self.assertGreater(widths["自然语言处理"], widths["AI"])
        self.assertGreaterEqual(widths["自然语言处理"], 88)

    def test_node_labels_are_escaped_in_svg(self):
        concept = knowledge.create_concept("A&B <研究>", "escaped")

        svg, _ = graph.render_svg(concept["id"])

        self.assertIn("A&amp;B &lt;研究&gt;", svg)
        self.assertNotIn("A&B <研究>", svg)

    def test_relation_labels_are_rendered_in_chinese(self):
        first = knowledge.create_concept("主题甲", "first")
        second = knowledge.create_concept("主题乙", "second")
        knowledge.create_relation(first["id"], second["id"], "related_to")

        svg, _ = graph.render_svg(first["id"])

        self.assertIn(">相关</text>", svg)
        self.assertNotIn(">related_to</text>", svg)
