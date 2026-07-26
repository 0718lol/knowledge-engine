"""Conservative hypothesis verdicts based on claim-aligned graph evidence."""
from evidence import analyze as evidence_analyze
from issues import match_claims


LEVEL_SCORES = {"strong": 0.9, "moderate": 0.7, "weak": 0.5}


def verify(statement):
    analysis = evidence_analyze(statement)
    claim = analysis["parsed_claim"]
    supports = analysis["supports"]
    contradicts = analysis["contradicts"]

    if not claim["mentioned_concepts"]:
        status = "unknown"
        match_score = 0
        rationale = "没有识别到本地知识库中的概念。"
    elif not claim["complete"]:
        status = "inconclusive"
        match_score = 0
        rationale = "命题缺少可识别的主体、关系或客体。"
    else:
        support_score = _best_score(supports)
        contradict_score = _best_score(contradicts)
        if support_score and support_score >= contradict_score + 0.1:
            status = "supports"
            match_score = support_score
            rationale = "当前知识库存在与命题方向一致的关系证据。"
        elif contradict_score and contradict_score >= support_score + 0.1:
            status = "contradicts"
            match_score = contradict_score
            rationale = "当前知识库存在与命题冲突或方向相反的关系证据。"
        else:
            status = "inconclusive"
            match_score = max(support_score, contradict_score)
            rationale = "当前证据不足，或支持与反对信号无法区分。"

    summary = {
        "parsed_claim": claim,
        "rationale": rationale,
        "supports": supports[:5],
        "contradicts": contradicts[:5],
        "counterexamples": analysis["counterexamples"][:3],
        "context_relations": analysis["context_relations"][:5],
        "context_evidence": analysis["context_evidence"][:5],
        "open_questions": analysis["open_questions"][:5],
        "related_concepts": analysis["related_concepts"],
        "related_papers": analysis["related_papers"][:5],
        "overall_level": analysis["overall_level"],
        "limitations": analysis["limitations"],
        "score_label": "证据匹配度",
        "curated_claims": match_claims(statement),
    }
    return create_hypothesis(statement, status, round(match_score, 3), summary)


def _best_score(items):
    if not items:
        return 0
    scores = []
    for item in items:
        base = LEVEL_SCORES.get(item.get("level"), 0.4)
        confidence = float(item.get("confidence", 0.5))
        score = min(base, confidence)
        if item.get("match_kind") == "inferred":
            score = min(score, 0.6)
        scores.append(score)
    return max(scores)


def create_hypothesis(statement, result, confidence, evidence_summary):
    from knowledge import create_hypothesis as _create
    return _create(statement, result, confidence, evidence_summary)
