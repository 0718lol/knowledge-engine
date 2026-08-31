import sqlite3

import database
import fulltext
import knowledge
import papers
import search
import evidence
import paths
import reasoning
import issues
import briefs
from arxiv import ARXIV_SEARCH_URL
from server import clean_string_list, clean_url, int_query

from tests.support import DatabaseTestCase


class DataContractTests(DatabaseTestCase):
    def test_external_paper_search_uses_tls(self):
        self.assertTrue(ARXIV_SEARCH_URL.startswith("https://"))

    def test_self_relation_is_rejected(self):
        concept = knowledge.create_concept("概念", "描述")
        with self.assertRaises(ValueError):
            knowledge.create_relation(concept["id"], concept["id"], "related_to")

    def test_database_trigger_rejects_invalid_confidence(self):
        first = knowledge.create_concept("甲", "描述")
        second = knowledge.create_concept("乙", "描述")
        with self.assertRaises(sqlite3.IntegrityError):
            with database.connection() as conn:
                conn.execute(
                    """INSERT INTO relations
                       (id, source_id, target_id, relation_type, evidence, confidence, created_at)
                       VALUES ('bad', ?, ?, 'related_to', '', 2, 'now')""",
                    (first["id"], second["id"]),
                )

    def test_combined_search_filter(self):
        knowledge.create_concept("机器学习", "学习算法", "人工智能")
        knowledge.create_concept("行为学习", "生物学习过程", "生物学")
        results = search.search("学习", category="生物学")
        self.assertEqual(["行为学习"], [item["name"] for item in results])

    def test_paper_count_tracks_filtered_items(self):
        papers.create_paper("Graph Learning", ["A"])
        papers.create_paper("Cell Biology", ["B"])
        self.assertEqual(2, papers.count_papers())
        self.assertEqual(1, papers.count_papers("Graph"))

    def test_paper_metadata_is_normalized(self):
        paper = papers.create_paper(
            " Paper ", [" Author "], year="2024", doi="https://doi.org/10.1000/ABC"
        )
        self.assertEqual("Paper", paper["title"])
        self.assertEqual(["Author"], paper["authors"])
        self.assertEqual(2024, paper["year"])
        self.assertEqual("10.1000/abc", paper["doi"])
        self.assertEqual(paper["id"], papers.get_paper_by_doi("10.1000/ABC")["id"])

    def test_invalid_paper_metadata_is_rejected(self):
        with self.assertRaises(ValueError):
            papers.create_paper("", [])
        with self.assertRaises(ValueError):
            papers.create_paper("Paper", [], year="unknown")

    def test_fulltext_chunk_parameters_are_validated(self):
        paper = papers.create_paper("Paper", ["A"])
        with self.assertRaises(ValueError):
            fulltext.chunk_paper(paper["id"], "some text", chunk_size=10, overlap=10)

    def test_fulltext_chunks_preserve_original_prose(self):
        paper = papers.create_paper("Paper", ["A"])
        text = "中文标点不会丢失。English punctuation stays, too."
        fulltext.chunk_paper(paper["id"], text, chunk_size=18, overlap=4)
        chunks = papers.get_chunks(paper["id"])
        self.assertGreater(len(chunks), 1)
        self.assertIn("。", chunks[0]["content"])

    def test_url_validation(self):
        self.assertEqual("https://example.com/a", clean_url("https://example.com/a"))
        with self.assertRaises(ValueError):
            clean_url("javascript:alert(1)")

    def test_integer_query_validation(self):
        self.assertEqual(20, int_query({"limit": ["20"]}, "limit", 50, 1, 100))
        with self.assertRaises(ValueError):
            int_query({"limit": ["101"]}, "limit", 50, 1, 100)

    def test_string_list_validation(self):
        self.assertEqual(["AI", "科学"], clean_string_list([" AI ", "科学"], "标签"))
        with self.assertRaises(ValueError):
            clean_string_list([{"name": "AI"}], "标签")

    def test_bundled_seed_has_no_self_relations(self):
        self.seed()
        with database.connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM relations WHERE source_id = target_id").fetchone()[0]
        self.assertEqual(0, count)

    def test_bundled_seed_uses_canonical_relation_direction(self):
        self.seed()
        with database.connection() as conn:
            row = conn.execute(
                """SELECT cs.name AS source_name, ct.name AS target_name
                   FROM relations r JOIN concepts cs ON cs.id = r.source_id
                   JOIN concepts ct ON ct.id = r.target_id
                   WHERE r.relation_type = 'is_a' AND cs.name = '深度学习' AND ct.name = '机器学习'"""
            ).fetchone()
        self.assertIsNotNone(row)

    def test_research_paths_are_distinct_and_idempotent(self):
        self.seed()
        analysis = evidence.analyze("深度学习是机器学习的一种")
        hypothesis = reasoning.verify("深度学习是机器学习的一种")
        first = paths.generate(analysis, hypothesis["id"])
        second = paths.generate(analysis, hypothesis["id"])
        self.assertGreaterEqual(len(first), 2)
        self.assertEqual([item["id"] for item in first], [item["id"] for item in second])
        self.assertEqual(len(first), len({item["path_label"] for item in first}))

    def test_only_one_research_path_can_be_selected(self):
        self.seed()
        analysis = evidence.analyze("深度学习是机器学习的一种")
        hypothesis = reasoning.verify("深度学习是机器学习的一种")
        generated = paths.generate(analysis, hypothesis["id"])
        paths.select_path(generated[0]["id"])
        paths.select_path(generated[1]["id"])
        stored = paths.get_paths_for_hypothesis(hypothesis["id"])
        self.assertEqual(1, sum(bool(item["is_selected"]) for item in stored))

    def test_schema_version_is_recorded(self):
        with database.connection() as conn:
            version = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()[0]
        self.assertEqual(str(database.SCHEMA_VERSION), version)

    def test_curated_seed_adds_structured_dossiers(self):
        self.seed()
        concept = knowledge.get_concept_by_name("AI辅助科学发现")
        detailed = knowledge.get_concept(concept["id"])
        self.assertGreaterEqual(len(detailed["sections"]), 4)
        self.assertEqual(
            {"importance", "mechanism", "boundary", "question"},
            {section["section_type"] for section in detailed["sections"]},
        )

    def test_curated_seed_is_idempotent(self):
        self.seed()
        self.seed()
        with database.connection() as conn:
            duplicates = conn.execute(
                """SELECT concept_id, section_type, title, COUNT(*) AS total
                   FROM concept_sections GROUP BY concept_id, section_type, title
                   HAVING total > 1"""
            ).fetchall()
        self.assertEqual([], duplicates)

    def test_curated_issue_contains_competing_claims_and_evidence(self):
        self.seed()
        issue_list = issues.list_issues()
        self.assertEqual(1, len(issue_list))
        issue = issues.get_issue(issue_list[0]["id"])
        self.assertEqual(4, len(issue["claims"]))
        self.assertEqual(
            {"supports", "challenges", "qualifies"},
            {claim["position"] for claim in issue["claims"]},
        )
        self.assertTrue(all(claim["evidence"] for claim in issue["claims"]))

    def test_curated_claim_match_is_context_only(self):
        self.seed()
        statement = "人工智能可以独立完成科学发现吗"
        matches = issues.match_claims(statement)
        self.assertTrue(matches)
        result = reasoning.verify(statement)
        summary = result["evidence_summary"]
        self.assertEqual("inconclusive", result["result"])
        self.assertTrue(summary["curated_claims"])

    def test_research_brief_assembles_curated_evidence(self):
        self.seed()
        brief = briefs.build("AI 能否独立完成科学发现？")
        self.assertEqual("curated", brief["status"])
        self.assertEqual("AI 能否独立完成科学发现？", brief["issue"]["title"])
        self.assertGreaterEqual(brief["coverage"]["claims"], 4)
        self.assertGreaterEqual(brief["coverage"]["sources"], 2)
        self.assertTrue(brief["open_questions"])

    def test_research_brief_does_not_invent_unknown_coverage(self):
        self.seed()
        brief = briefs.build("火星农业税收制度如何设计？")
        self.assertEqual("insufficient", brief["status"])
        self.assertEqual([], brief["concepts"])
        self.assertIn("没有", brief["assessment"])
