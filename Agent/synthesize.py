import argparse
import json
import time
from pathlib import Path
from typing import Any

import ollama

from schema import AppResearch


# ============================================================
# PATHS / CONFIG
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_EVIDENCE_FILE = PROJECT_ROOT / "data" / "raw_evidence.json"
RESULTS_FILE = PROJECT_ROOT / "data" / "results.json"

MODEL = "qwen3:8b"

# Keep the local model output small.
MAX_OUTPUT_TOKENS = 400
NUM_CTX = 8192

# One local Qwen call at a time is the safe default on a
# 16 GB M3 Mac. Do not add concurrency until measured.
DEFAULT_LIMIT = None


# ============================================================
# FILE HELPERS
# ============================================================

def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise RuntimeError(
            f"Could not read {path}: {e}"
        ) from e


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix(path.suffix + ".tmp")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )

    tmp_path.replace(path)


# ============================================================
# PROMPT / EVIDENCE
# ============================================================

def build_prompt(
    app: str,
    category: str,
    evidence: list[dict],
) -> str:
    blocks = []

    for item in evidence:
        blocks.append(
            f"""
SOURCE {item["id"]}
Title: {item.get("title", "")}
URL: {item.get("url", "")}
Evidence:
{item.get("evidence_text", "")}
""".strip()
        )

    evidence_text = "\n\n".join(blocks)

    return f"""
You are a careful API integration research analyst.

Application: {app}
Category: {category}

Use ONLY the supplied evidence.

Return a structured research record.

FIELDS:
- description
- auth_methods
- access_model
- access_reason
- api_surface
- mcp_status
- buildability
- blocker
- confidence
- evidence_refs

CRITICAL RULES

1. Do not use outside knowledge.
2. Do not invent facts or URLs.
3. API existence does NOT automatically mean self-serve access.
4. API permissions do NOT automatically mean access is gated.
5. OAuth does NOT automatically imply self-serve or gated access.

ACCESS MODEL

Use "Self-serve" ONLY if the evidence explicitly supports
developer access / credential acquisition without a sales,
partnership, approval, or otherwise unestablished access barrier.

Use "Gated" ONLY if the evidence explicitly indicates:
- enterprise restriction,
- paid-plan restriction,
- sales/contact-sales requirement,
- approval requirement,
- partnership requirement,
- admin approval,
or a similar access barrier.

Otherwise use "Unknown".

MCP

Use "Official" ONLY if the supplied evidence explicitly
supports an official MCP implementation or official MCP support.

Use "Community" ONLY for clearly identified third-party/community
MCP implementations.

If the evidence only explains what MCP is, but does not establish
an implementation for this application, use "Unknown".

Buildability

Use:
- "Buildable today"
- "Partially buildable"
- "Blocked"
- "Needs verification"

If the evidence is insufficient to establish buildability,
use "Needs verification".

CONFIDENCE

- High: direct, strong evidence, preferably official
- Medium: useful evidence with some ambiguity
- Low: weak, conflicting, or incomplete evidence

EVIDENCE REFS

Return only the SOURCE numbers that materially support your
conclusions.

Do not reproduce evidence text.
Do not reproduce URLs.

Return ONLY valid JSON matching the supplied schema.
No Markdown.
No explanation outside the JSON.

EVIDENCE

{evidence_text}
""".strip()


# ============================================================
# EVIDENCE QUALITY GUARDS
# ============================================================

def _support_text(
    evidence: list[dict],
    refs: list[int],
) -> str:
    ref_set = set(refs)

    parts = [
        item.get("evidence_text", "")
        for item in evidence
        if item.get("id") in ref_set
    ]

    return " ".join(parts).lower()


def apply_conservative_guards(
    result: AppResearch,
    evidence: list[dict],
) -> AppResearch:
    """
    Lightweight deterministic guardrails for failure modes we've
    already observed during the Salesforce prototype.

    These do NOT try to replace the LLM. They only downgrade
    obviously unsupported classifications.
    """

    support = _support_text(
        evidence,
        result.evidence_refs,
    )

    # --------------------------------------------------------
    # MCP guard
    # --------------------------------------------------------

    if result.mcp_status == "Official":

        explicit_mcp_terms = (
            "official mcp",
            "mcp server",
            "mcp support",
            "model context protocol server",
            "model context protocol support",
        )

        has_explicit_mcp = any(
            term in support
            for term in explicit_mcp_terms
        )

        if not has_explicit_mcp:
            result.mcp_status = "Unknown"

    # --------------------------------------------------------
    # Access-model guard
    # --------------------------------------------------------

    if result.access_model in {
        "Self-serve",
        "Gated",
    }:

        access_terms = (
            "developer account",
            "developer access",
            "sign up",
            "signup",
            "register",
            "registration",
            "self-serve",
            "self serve",
            "contact sales",
            "sales team",
            "enterprise",
            "approval",
            "approve",
            "paid plan",
            "pricing plan",
            "subscription",
            "partner",
            "partnership",
            "credentials",
            "api key",
            "client id",
            "client secret",
            "access token",
        )

        if not any(
            term in support
            for term in access_terms
        ):
            result.access_model = "Unknown"
            result.access_reason = (
                "Evidence did not explicitly establish "
                "whether developer access is self-serve or gated."
            )

    return result


# ============================================================
# ONE APP
# ============================================================

def synthesize_one(app_record: dict) -> dict:
    app = app_record["app"]
    category = app_record.get("category", "")

    evidence = app_record.get("evidence", [])

    if not evidence:
        raise RuntimeError(
            f"{app}: no evidence available."
        )

    # Number evidence locally for the LLM.
    numbered_evidence = []

    for idx, item in enumerate(evidence, start=1):
        numbered_evidence.append({
            "id": idx,
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "evidence_text": item.get(
                "evidence_text",
                "",
            ),
        })

    prompt = build_prompt(
        app=app,
        category=category,
        evidence=numbered_evidence,
    )

    start = time.time()

    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        format=AppResearch.model_json_schema(),
        think=False,
        options={
            "temperature": 0,
            "num_predict": MAX_OUTPUT_TOKENS,
            "num_ctx": NUM_CTX,
        },
    )

    elapsed = time.time() - start

    raw = response["message"]["content"]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"{app}: invalid JSON from Qwen: {e}"
        ) from e

    try:
        parsed = AppResearch.model_validate(data)
    except Exception as e:
        raise RuntimeError(
            f"{app}: Pydantic validation failed: {e}"
        ) from e

    # Deterministic guardrails.
    parsed = apply_conservative_guards(
        parsed,
        numbered_evidence,
    )

    # --------------------------------------------------------
    # Resolve evidence refs to actual evidence objects
    # --------------------------------------------------------

    evidence_map = {
        item["id"]: {
            "title": item["title"],
            "url": item["url"],
            "evidence_text": item["evidence_text"],
        }
        for item in numbered_evidence
    }

    selected_evidence = []

    invalid_refs = []

    for ref in parsed.evidence_refs:
        if ref in evidence_map:
            selected_evidence.append(
                evidence_map[ref]
            )
        else:
            invalid_refs.append(ref)

    if invalid_refs:
        raise RuntimeError(
            f"{app}: invalid evidence refs "
            f"{invalid_refs}"
        )

    final_result = parsed.model_dump()

    # evidence_refs are an internal mechanism; the final dataset
    # contains the actual supporting evidence.
    final_result.pop(
        "evidence_refs",
        None,
    )

    final_result["evidence"] = selected_evidence

    # Helpful internal metadata for later analysis/debugging.
    final_result["_meta"] = {
        "source_count": len(evidence),
        "llm_seconds": round(elapsed, 2),
        "guardrails_applied": True,
    }

    return final_result


# ============================================================
# RESUMABLE RUN
# ============================================================

def load_existing_results() -> dict[str, dict]:
    """
    Load existing results keyed by app name so the job can resume.
    """

    data = load_json(
        RESULTS_FILE,
        default=[],
    )

    if not isinstance(data, list):
        return {}

    return {
        item.get("app"): item
        for item in data
        if item.get("app")
    }


def save_results_map(
    results_map: dict[str, dict],
) -> None:
    ordered = list(
        results_map.values()
    )

    ordered.sort(
        key=lambda item: item.get(
            "app",
            "",
        ).lower()
    )

    save_json(
        RESULTS_FILE,
        ordered,
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Synthesize raw app research into "
            "validated structured results."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=(
            "Process only the first N unfinished apps."
        ),
    )

    args = parser.parse_args()

    raw = load_json(
        RAW_EVIDENCE_FILE,
        default=None,
    )

    if not isinstance(raw, list):
        raise RuntimeError(
            f"Expected a list in {RAW_EVIDENCE_FILE}"
        )

    existing = load_existing_results()

    remaining = [
        item
        for item in raw
        if item.get("app") not in existing
    ]

    if args.limit:
        remaining = remaining[:args.limit]

    total_raw = len(raw)
    already_done = total_raw - len([
        item
        for item in raw
        if item.get("app") not in existing
    ])

    print("\n" + "=" * 68)
    print("QWEN SYNTHESIS")
    print("=" * 68)
    print(f"Total raw apps:     {total_raw}")
    print(f"Already completed:  {already_done}")
    print(f"Remaining this run: {len(remaining)}")
    print(f"Model:              {MODEL}")
    print("=" * 68)

    if not remaining:
        print("\nNothing to synthesize.")
        return

    run_start = time.time()

    successes = 0
    failures = 0

    for index, app_record in enumerate(
        remaining,
        start=1,
    ):

        app = app_record.get(
            "app",
            "Unknown",
        )

        print(
            f"\n[{index}/{len(remaining)}] {app}"
        )

        try:

            result = synthesize_one(
                app_record
            )

            existing[app] = result
            save_results_map(existing)

            successes += 1

            llm_seconds = result.get(
                "_meta",
                {},
            ).get(
                "llm_seconds",
                0,
            )

            print(
                f"  ✓ saved | "
                f"Qwen: {llm_seconds:.1f}s | "
                f"progress: "
                f"{successes + failures}/"
                f"{len(remaining)}"
            )

        except Exception as error:

            failures += 1

            print(
                f"  ✗ FAILED: {error}"
            )

            # Keep going. A single problematic app must not
            # kill the entire 100-app run.
            continue

    elapsed = time.time() - run_start

    print("\n" + "=" * 68)
    print("SYNTHESIS COMPLETE")
    print("=" * 68)
    print(f"Successful this run: {successes}")
    print(f"Failed this run:     {failures}")
    print(f"Total results now:   {len(existing)}")
    print(
        f"Wall-clock time:    "
        f"{elapsed:.1f}s "
        f"({elapsed / 60:.1f} min)"
    )
    print(f"Output:              {RESULTS_FILE}")
    print("=" * 68)


if __name__ == "__main__":
    main()