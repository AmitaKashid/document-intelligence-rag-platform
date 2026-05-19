from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from evaluation.dataset_generator import generate_dynamic_eval_dataset
from evaluation.runner import run_evaluation, summarize_results


BASE_DIR = Path(__file__).resolve().parents[1]

STATIC_EVAL_FILE = BASE_DIR / "data" / "eval_questions.json"
DYNAMIC_EVAL_FILE = BASE_DIR / "data" / "eval_questions_dynamic.json"

RESULTS_DIR = BASE_DIR / "evaluation" / "results"

USE_DYNAMIC_DATASET = False
NUM_DYNAMIC_QUESTIONS = 5

STRATEGIES = [
    "section_aware",
    "recursive",
    "parent_child",
    "table_preserving",
]

TOP_K_VALUES = [3, 5]

PROVIDER = "compatible"
CHAT_URL = "http://127.0.0.1:8000/api/chat"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        return

    ignored_fields = {
        "generated_answer",
        "returned_sources",
        "unsupported_claims",
    }

    fieldnames = [key for key in rows[0].keys() if key not in ignored_fields]

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            clean_row = {key: row.get(key) for key in fieldnames}
            writer.writerow(clean_row)


async def main() -> None:
    if USE_DYNAMIC_DATASET:
        print("Generating dynamic evaluation dataset from indexed document chunks...")

        generate_dynamic_eval_dataset(
            output_path=DYNAMIC_EVAL_FILE,
            num_questions=NUM_DYNAMIC_QUESTIONS,
        )

        eval_file = DYNAMIC_EVAL_FILE
    else:
        eval_file = STATIC_EVAL_FILE

    print("Starting RAG evaluation...")
    print(f"Evaluation file: {eval_file}")
    print(f"Chat endpoint: {CHAT_URL}")
    print(f"Strategies: {STRATEGIES}")
    print(f"Top-k values: {TOP_K_VALUES}")

    results = await run_evaluation(
        eval_file=eval_file,
        strategies=STRATEGIES,
        top_k_values=TOP_K_VALUES,
        provider=PROVIDER,
        chat_url=CHAT_URL,
    )

    summary = summarize_results(results)

    write_json(RESULTS_DIR / "eval_results.json", results)
    write_json(RESULTS_DIR / "eval_summary.json", summary)
    write_csv(RESULTS_DIR / "eval_results.csv", results)
    write_csv(RESULTS_DIR / "eval_summary.csv", summary)

    print("\nEvaluation complete.")
    print(f"Detailed results: {RESULTS_DIR / 'eval_results.json'}")
    print(f"Summary results:  {RESULTS_DIR / 'eval_summary.json'}")

    print("\nBest configurations:")
    for row in summary[:5]:
        print(
            f"- strategy={row['strategy']}, "
            f"top_k={row['top_k']}, "
            f"overall={row['avg_overall_score']}, "
            f"retrieval={row['avg_retrieval_hit']}, "
            f"groundedness={row['avg_groundedness']}, "
            f"citation={row['avg_citation_accuracy']}, "
            f"latency_ms={row['avg_latency_ms']}"
        )


if __name__ == "__main__":
    asyncio.run(main())