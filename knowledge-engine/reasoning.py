"""Hypothesis verification engine: delegates to evidence analysis for strict results."""
import re
from database import connection
from search import search
from evidence import analyze as evidence_analyze


def _tokenize(text):
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    for block in re.findall(r"[一-鿿]+", text.lower()):
        tokens.add(block)
        tokens.update(block[i:i + 2] for i in range(len(block) - 1))
    return tokens


def verify(statement):
    """Evaluate a hypothesis statement using the strict evidence analysis engine.

    Returns a verdict dict with evidence levels, counterexamples, and open questions.
    """
    analysis = evidence_analyze(statement)

    if not analysis.get("related_concepts"):
        result = create_hypothesis(statement, "unknown", 0, {})
        return result

    supports = analysis.get("supports", [])
    contradicts = analysis.get("contradicts", [])

    support_score = sum(1 for s in supports if s["level"] in ("strong", "moderate"))
    contradict_score = sum(1 for c in contradicts if c["level"] in ("strong", "moderate"))

    if support_score > contradict_score:
        status = "supports"
        confidence = support_score / max(support_score + contradict_score, 1)
    elif contradict_score > support_score:
        status = "contradicts"
        confidence = contradict_score / max(support_score + contradict_score, 1)
    else:
        status = "inconclusive"
        confidence = 0.5

    evidence_summary = {
        "supports": supports[:5],
        "contradicts": contradicts[:5],
        "counterexamples": analysis.get("counterexamples", [])[:3],
        "open_questions": analysis.get("open_questions", [])[:5],
        "related_concepts": analysis.get("related_concepts", []),
        "related_papers": analysis.get("related_papers", [])[:5],
        "overall_level": analysis.get("overall_level", "none"),
    }

    return create_hypothesis(statement, status, round(confidence, 3), evidence_summary)


def create_hypothesis(statement, result, confidence, evidence_summary):
    from knowledge import create_hypothesis as _create
    return _create(statement, result, confidence, evidence_summary)