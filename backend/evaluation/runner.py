from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from evaluation.metrics import evaluate_single_result


DEFAULT_CHAT_URL = "http://127.0.0.1:8000/api/chat"


def load_eval_questions(path: str | Path) -> List[Dict[str, Any]]:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Evaluation file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Evaluation file must contain a JSON list.")

    return data


def safe_get_answer(response_json: Dict[str, Any]) -> str:
    """
    Supports different response shapes from your backend.
    """
    return str(
        response_json.get("answer")
        or response_json.get("response")
        or response_json.get("message")
        or ""
    )


def safe_get_sources(response_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Supports different source field names.
    """
    sources = (
        response_json.get("sources")
        or response_json.get("citations")
        or response_json.get("source_documents")
        or []
    )

    if isinstance(sources, list):
        return [s for s in sources if isinstance(s, dict)]

    return []


def safe_get_contexts(response_json: Dict[str, Any]) -> List[str]:
    """
    Extracts retrieved chunk text from common response formats.
    """
    contexts: List[str] = []

    raw_contexts = (
        response_json.get("contexts")
        or response_json.get("retrieved_contexts")
        or response_json.get("chunks")
        or []
    )

    if isinstance(raw_contexts, list):
        for item in raw_contexts:
            if isinstance(item, str):
                contexts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or item.get("page_content")
                if text:
                    contexts.append(str(text))

    sources = safe_get_sources(response_json)
    for source in sources:
        text = (
            source.get("text")
            or source.get("content")
            or source.get("page_content")
            or source.get("chunk_text")
            or source.get("document_text")
        )
        if text:
            contexts.append(str(text))

    return contexts


async def call_chat_endpoint(
    question: str,
    strategy: str,
    provider: str,
    limit: int,
    chat_url: str = DEFAULT_CHAT_URL,
    timeout_seconds: int = 120,
) -> Dict[str, Any]:
    """
    Calls your existing /api/chat endpoint.

    This means we do not need to rewrite your RAG pipeline.
    We evaluate it as a black box.
    """
    payload = {
        "question": question,
        "strategy": strategy,
        "provider": provider,
        "limit": limit,
    }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        started = time.perf_counter()
        response = await client.post(chat_url, json=payload)
        latency_ms = (time.perf_counter() - started) * 1000

    response.raise_for_status()
    data = response.json()
    data["_measured_latency_ms"] = latency_ms

    return data


async def run_evaluation(
    eval_file: str | Path,
    strategies: List[str],
    top_k_values: List[int],
    provider: str = "compatible",
    chat_url: str = DEFAULT_CHAT_URL,
) -> List[Dict[str, Any]]:
    test_cases = load_eval_questions(eval_file)
    results: List[Dict[str, Any]] = []

    for strategy in strategies:
        for top_k in top_k_values:
            for test_case in test_cases:
                question = test_case["question"]
                print(
                    f"[EVAL] strategy={strategy} | top_k={top_k} | "
                    f"question_id={test_case.get('id')} | question={question[:80]}",
                    flush=True,
                )
                try:
                    raw_response = await call_chat_endpoint(
                        question=question,
                        strategy=strategy,
                        provider=provider,
                        limit=top_k,
                        chat_url=chat_url,
                    )
                    print(
                        f"[DONE] strategy={strategy} | top_k={top_k} | "
                        f"question_id={test_case.get('id')}",
                        flush=True,
                    )
                    answer = safe_get_answer(raw_response)
                    sources = safe_get_sources(raw_response)
                    contexts = safe_get_contexts(raw_response)
                    latency_ms = float(raw_response.get("_measured_latency_ms", 0.0))

                    metrics = evaluate_single_result(
                        test_case=test_case,
                        generated_answer=answer,
                        retrieved_sources=sources,
                        returned_sources=sources,
                        retrieved_contexts=contexts,
                        latency_ms=latency_ms,
                    )

                    result = {
                        "strategy": strategy,
                        "top_k": top_k,
                        "provider": provider,
                        **metrics,
                        "generated_answer": answer,
                        "returned_sources": sources,
                    }

                except Exception as exc:
                    result = {
                        "strategy": strategy,
                        "top_k": top_k,
                        "provider": provider,
                        "question_id": test_case.get("id"),
                        "question": question,
                        "error": str(exc),
                        "answer_correctness": 0.0,
                        "groundedness_score": 0.0,
                        "citation_accuracy": 0.0,
                        "retrieval_hit": 0.0,
                        "source_recall": 0.0,
                        "mrr": 0.0,
                        "latency_ms": 0.0,
                        "overall_score": 0.0,
                    }

                results.append(result)

    return results


def summarize_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Aggregates scores by strategy and top_k.
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}

    for row in results:
        key = f"{row['strategy']}__topk_{row['top_k']}"
        groups.setdefault(key, []).append(row)

    summary: List[Dict[str, Any]] = []

    for key, rows in groups.items():
        count = len(rows)

        def avg(field: str) -> float:
            values = [float(r.get(field, 0.0)) for r in rows]
            return round(sum(values) / count, 4) if count else 0.0

        first = rows[0]

        summary.append(
            {
                "strategy": first["strategy"],
                "top_k": first["top_k"],
                "provider": first["provider"],
                "num_questions": count,
                "avg_overall_score": avg("overall_score"),
                "avg_retrieval_hit": avg("retrieval_hit"),
                "avg_source_recall": avg("source_recall"),
                "avg_mrr": avg("mrr"),
                "avg_answer_correctness": avg("answer_correctness"),
                "avg_groundedness": avg("groundedness_score"),
                "avg_citation_accuracy": avg("citation_accuracy"),
                "avg_latency_ms": avg("latency_ms"),
            }
        )

    summary.sort(key=lambda x: x["avg_overall_score"], reverse=True)
    return summary