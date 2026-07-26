import json

import knowledge
import papers
import reasoning

from tests.support import DatabaseTestCase


class ReasoningTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.ml = knowledge.create_concept("机器学习", "从数据中学习", "人工智能")
        self.deep = knowledge.create_concept("深度学习", "多层神经网络", "人工智能")
        self.ai = knowledge.create_concept("人工智能", "机器智能", "人工智能")
        knowledge.create_relation(
            self.deep["id"], self.ml["id"], "is_a", "深度学习是机器学习的子领域", 0.95
        )

    def summary(self, result):
        value = result["evidence_summary"]
        return json.loads(value) if isinstance(value, str) else value

    def test_direct_directional_claim_is_supported(self):
        result = reasoning.verify("深度学习是机器学习的一种")
        self.assertEqual("supports", result["result"])
        self.assertGreaterEqual(result["confidence"], 0.8)
        self.assertEqual("direct", self.summary(result)["supports"][0]["match_kind"])

    def test_reverse_taxonomy_claim_is_contradicted(self):
        result = reasoning.verify("机器学习是深度学习的一种")
        self.assertEqual("contradicts", result["result"])

    def test_missing_relation_is_inconclusive(self):
        result = reasoning.verify("深度学习依赖机器学习")
        self.assertEqual("inconclusive", result["result"])
        self.assertEqual(0, result["confidence"])

    def test_negated_direct_claim_is_contradicted(self):
        result = reasoning.verify("深度学习不属于机器学习的一种")
        self.assertEqual("contradicts", result["result"])

    def test_incomplete_claim_does_not_receive_a_directional_verdict(self):
        result = reasoning.verify("深度学习很重要")
        self.assertEqual("inconclusive", result["result"])

    def test_related_paper_is_context_not_support(self):
        paper = papers.create_paper("A recent paper", ["A"], year=2026, abstract="深度学习研究")
        papers.link_paper_to_concept(paper["id"], self.deep["id"])
        result = reasoning.verify("深度学习依赖机器学习")
        summary = self.summary(result)
        self.assertEqual("inconclusive", result["result"])
        self.assertEqual([], summary["supports"])
        self.assertEqual(1, len(summary["related_papers"]))

    def test_transitive_taxonomy_is_labeled_as_inference(self):
        knowledge.create_relation(self.ml["id"], self.ai["id"], "is_a", "机器学习属于人工智能", 0.95)
        result = reasoning.verify("深度学习是人工智能的一种")
        summary = self.summary(result)
        self.assertEqual("supports", result["result"])
        self.assertLessEqual(result["confidence"], 0.6)
        self.assertEqual("inferred", summary["supports"][0]["match_kind"])
