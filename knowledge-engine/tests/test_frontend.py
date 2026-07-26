from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class _HTMLInventory(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.assets = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"])
        if tag in ("script", "link"):
            self.assets.append(values.get("src") or values.get("href") or "")


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        cls.css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
        cls.js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        cls.inventory = _HTMLInventory()
        cls.inventory.feed(cls.html)

    def test_html_ids_are_unique(self):
        self.assertEqual(len(self.inventory.ids), len(set(self.inventory.ids)))

    def test_static_assets_are_local(self):
        self.assertTrue(all(not asset.startswith(("http://", "https://")) for asset in self.inventory.assets))
        self.assertNotIn("@import", self.css)
        self.assertNotIn("googleapis", self.css)

    def test_javascript_static_id_references_exist(self):
        referenced = set(re.findall(r"\$\('#([a-z0-9-]+)'\)", self.js))
        dynamic = {"edit-concept-btn", "add-relation-btn", "add-evidence-btn"}
        self.assertEqual(set(), referenced - set(self.inventory.ids) - dynamic)

    def test_new_tab_links_block_opener_access(self):
        link_templates = re.findall(r"<a\s+[^>]*target=\\?\"_blank\\?\"[^>]*>", self.js)
        self.assertTrue(link_templates)
        self.assertTrue(all("noopener noreferrer" in link for link in link_templates))
