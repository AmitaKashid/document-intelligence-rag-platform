from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9äöüß\s]", " ", text)
    return text.strip()


def tokenize(text: Optional[str]) -> List[str]:
    text = normalize_text(text)
    if not text:
        return []
    return [t for t in text.split() if len(t) > 1]


def token_f1(reference: str, prediction: str) -> float:
    """
    Measures lexical similarity between expected answer and generated answer.

    This is not perfect semantic evaluation, but it is stable, cheap,
    and useful as a first automatic correctness signal.
    """
    ref_tokens = tokenize(reference)
    pred_tokens = tokenize(prediction)

    if not ref_tokens or not pred_tokens:
        return 0.0

    ref_counts: Dict[str, int] = {}
    pred_counts: Dict[str, int] = {}

    for token in ref_tokens:
        ref_counts[token] = ref_counts.get(token, 0) + 1

    for token in pred_tokens:
        pred_counts[token] = pred_counts.get(token, 0) + 1

    overlap = 0
    for token, count in ref_counts.items():
        overlap += min(count, pred_counts.get(token, 0))

    if overlap == 0:
        return 0.0

    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)

    return 2 * precision * recall / (precision + recall)


def extract_sentences(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 10]


def source_matches(expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
    """
    Source match logic for PDF RAG evaluation.

    Primary match:
    - document name
    - page number

    Section title is only used when page is missing, because parsed section
    names may differ from human-written expected section labels.
    """
    expected_document = normalize_text(str(expected.get("document", "")))
    expected_section = normalize_text(str(expected.get("section", "")))
    expected_page = expected.get("page")

    actual_document = normalize_text(
        str(
            actual.get("document")
            or actual.get("document_name")
            or actual.get("file")
            or actual.get("filename")
            or actual.get("file_name")
            or actual.get("source")
            or ""
        )
    )

    actual_section = normalize_text(
        str(
            actual.get("section")
            or actual.get("section_title")
            or actual.get("heading")
            or actual.get("title")
            or ""
        )
    )

    actual_page = (
        actual.get("page")
        or actual.get("page_number")
        or actual.get("pageIndex")
        or actual.get("page_index")
        or actual.get("page_no")
        or actual.get("page_num")
    )

    # 1. Document must match if expected document is provided.
    if expected_document:
        document_ok = (
            expected_document in actual_document
            or actual_document in expected_document
        )
        if not document_ok:
            return False

    # 2. If expected page exists, page is the main source evidence.
    if expected_page not in [None, ""]:
        if actual_page in [None, ""]:
            return False

        try:
            expected_page_int = int(expected_page)
            actual_page_int = int(actual_page)

            # Allow exact page and +/- 1 because PDF page indexing can differ.
            return (
                expected_page_int == actual_page_int
                or expected_page_int == actual_page_int + 1
                or expected_page_int + 1 == actual_page_int
            )
        except Exception:
            return False

    # 3. If page is unavailable, fall back to section matching.
    if expected_section:
        return (
            expected_section in actual_section
            or actual_section in expected_section
        )

    # 4. If only document is expected, document match is enough.
    return True
def evaluate_retrieval(
    expected_sources: List[Dict[str, Any]],
    retrieved_sources: List[Dict[str, Any]],
) -> Dict[str, float]:
    """
    Evaluates whether the retriever brought back the expected source pages/sections.
    """
    if not expected_sources:
        return {
            "retrieval_hit": 0.0,
            "source_recall": 0.0,
            "mrr": 0.0,
        }

    if not retrieved_sources:
        return {
            "retrieval_hit": 0.0,
            "source_recall": 0.0,
            "mrr": 0.0,
        }

    matched_expected_count = 0
    first_match_rank: Optional[int] = None

    for expected in expected_sources:
        found = False

        for rank, actual in enumerate(retrieved_sources, start=1):
            if source_matches(expected, actual):
                found = True
                if first_match_rank is None:
                    first_match_rank = rank
                break

        if found:
            matched_expected_count += 1

    source_recall = matched_expected_count / len(expected_sources)
    retrieval_hit = 1.0 if matched_expected_count > 0 else 0.0
    mrr = 1.0 / first_match_rank if first_match_rank else 0.0

    return {
        "retrieval_hit": round(retrieval_hit, 4),
        "source_recall": round(source_recall, 4),
        "mrr": round(mrr, 4),
    }


def evaluate_citation_accuracy(
    expected_sources: List[Dict[str, Any]],
    returned_sources: List[Dict[str, Any]],
) -> float:
    """
    Evaluates whether the answer cites the correct page/document/section.
    """
    if not expected_sources or not returned_sources:
        return 0.0

    matched = 0

    for expected in expected_sources:
        if any(source_matches(expected, actual) for actual in returned_sources):
            matched += 1

    return round(matched / len(expected_sources), 4)


def evaluate_groundedness(answer: str, contexts: List[str]) -> Dict[str, Any]:
    """
    Lightweight groundedness proxy.

    It splits the answer into sentence-like claims and checks whether each claim
    has lexical overlap with at least one retrieved context.

    This is not as strong as an LLM judge, but it catches many obvious cases:
    - answer not based on retrieved context
    - answer contains unsupported extra claims
    - answer is generic despite retrieved evidence
    """
    claims = extract_sentences(answer)

    if not claims:
        return {
            "groundedness_score": 0.0,
            "supported_claim_ratio": 0.0,
            "unsupported_claims": [],
        }

    if not contexts:
        return {
            "groundedness_score": 0.0,
            "supported_claim_ratio": 0.0,
            "unsupported_claims": claims,
        }

    supported = 0
    unsupported_claims: List[str] = []

    for claim in claims:
        best_overlap = max(token_f1(context, claim) for context in contexts)

        if best_overlap >= 0.18:
            supported += 1
        else:
            unsupported_claims.append(claim)

    supported_ratio = supported / len(claims)

    return {
        "groundedness_score": round(supported_ratio, 4),
        "supported_claim_ratio": round(supported_ratio, 4),
        "unsupported_claims": unsupported_claims,
    }


def calculate_overall_score(
    retrieval_hit: float,
    source_recall: float,
    mrr: float,
    answer_correctness: float,
    groundedness: float,
    citation_accuracy: float,
    latency_ms: float,
) -> float:
    """
    Weighted score for selecting the best RAG configuration.

    We penalize very slow responses softly.
    """
    if latency_ms <= 0:
        latency_score = 1.0
    elif latency_ms <= 2000:
        latency_score = 1.0
    elif latency_ms <= 5000:
        latency_score = 0.7
    elif latency_ms <= 10000:
        latency_score = 0.4
    else:
        latency_score = 0.2

    retrieval_score = (0.50 * retrieval_hit) + (0.30 * source_recall) + (0.20 * mrr)

    overall = (
        0.30 * retrieval_score
        + 0.25 * answer_correctness
        + 0.20 * groundedness
        + 0.15 * citation_accuracy
        + 0.10 * latency_score
    )

    return round(overall, 4)


def evaluate_single_result(
    test_case: Dict[str, Any],
    generated_answer: str,
    retrieved_sources: List[Dict[str, Any]],
    returned_sources: List[Dict[str, Any]],
    retrieved_contexts: List[str],
    latency_ms: float,
) -> Dict[str, Any]:
    expected_answer = test_case.get("expected_answer", "")
    expected_sources = test_case.get("expected_sources", [])

    retrieval_metrics = evaluate_retrieval(expected_sources, retrieved_sources)
    citation_accuracy = evaluate_citation_accuracy(expected_sources, returned_sources)

    answer_correctness = round(token_f1(expected_answer, generated_answer), 4)
    groundedness_result = evaluate_groundedness(generated_answer, retrieved_contexts)

    overall_score = calculate_overall_score(
        retrieval_hit=retrieval_metrics["retrieval_hit"],
        source_recall=retrieval_metrics["source_recall"],
        mrr=retrieval_metrics["mrr"],
        answer_correctness=answer_correctness,
        groundedness=groundedness_result["groundedness_score"],
        citation_accuracy=citation_accuracy,
        latency_ms=latency_ms,
    )

    return {
        "question_id": test_case.get("id"),
        "question": test_case.get("question"),
        "answer_correctness": answer_correctness,
        "groundedness_score": groundedness_result["groundedness_score"],
        "supported_claim_ratio": groundedness_result["supported_claim_ratio"],
        "citation_accuracy": citation_accuracy,
        "retrieval_hit": retrieval_metrics["retrieval_hit"],
        "source_recall": retrieval_metrics["source_recall"],
        "mrr": retrieval_metrics["mrr"],
        "latency_ms": round(latency_ms, 2),
        "overall_score": overall_score,
        "unsupported_claims": groundedness_result["unsupported_claims"],
    }