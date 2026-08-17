import json
import time
from pathlib import Path

import ollama

from tools import web_search, format_search_evidence
from schema import AppResearch


# ============================================================
# CONFIGURATION
# ============================================================

MODEL = "qwen3:8b"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_FILE = PROJECT_ROOT / "data" / "results.json"

MAX_SEARCH_RESULTS = 2
MAX_EVIDENCE_ITEMS = 6
MAX_SNIPPET_CHARS = 700
MAX_OUTPUT_TOKENS = 400


# ============================================================
# SEARCH STRATEGY
# ============================================================

def build_queries(app: str) -> list[str]:
    """
    Three focused searches cover the main research dimensions.
    """

    return [
        f"{app} official API authentication developer documentation",
        f"{app} official API access permissions pricing developer",
        f"{app} official MCP Model Context Protocol",
    ]


# ============================================================
# EVIDENCE COLLECTION
# ============================================================

def collect_evidence(app: str) -> list[dict]:
    """
    Collect a small, focused evidence set for one app.
    """

    all_results = []
    seen_urls = set()

    queries = build_queries(app)

    print("\n" + "=" * 60)
    print(f"COLLECTING EVIDENCE: {app}")
    print("=" * 60)

    for index, query in enumerate(queries, start=1):

        print(f"\n[{index}/{len(queries)}] Searching:")
        print(f"  {query}")

        start = time.time()

        results = web_search(
            query,
            max_results=MAX_SEARCH_RESULTS,
        )

        elapsed = time.time() - start

        print(
            f"  → {len(results)} results "
            f"({elapsed:.1f}s)"
        )

        for result in results:

            url = result.get("url", "").strip()

            if not url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)

            all_results.append({
                "title": result.get("title", ""),
                "url": url,
                "snippet": result.get(
                    "snippet",
                    ""
                )[:MAX_SNIPPET_CHARS],
            })

    evidence = format_search_evidence(
        all_results
    )

    evidence = evidence[:MAX_EVIDENCE_ITEMS]

    print(
        f"\nEvidence collected: "
        f"{len(evidence)} sources"
    )

    numbered = []

    for index, item in enumerate(
        evidence,
        start=1,
    ):
        numbered.append({
            "id": index,
            "title": item["title"],
            "url": item["url"],
            "evidence_text": item["evidence_text"],
        })

    return numbered


# ============================================================
# PROMPT
# ============================================================

def build_prompt(
    app: str,
    category: str,
    evidence: list[dict],
) -> str:

    evidence_blocks = []

    for item in evidence:

        evidence_blocks.append(
            f"""
SOURCE {item["id"]}
Title: {item["title"]}
URL: {item["url"]}
Evidence:
{item["evidence_text"]}
""".strip()
        )

    evidence_text = "\n\n".join(
        evidence_blocks
    )

    return f"""
You are a careful API integration research analyst.

Application: {app}
Category: {category}

Use ONLY the evidence supplied below.

Determine:

1. Authentication methods
2. API access model
3. Reason for the access model
4. API surface
5. MCP status
6. Buildability for an integration platform
7. Blocker
8. Confidence

STRICT RULES:

- Do not use outside knowledge.
- Do not invent facts.
- Do not invent URLs.
- Do not infer unsupported claims.
- API existence does NOT automatically mean self-serve access.
- API permissions do NOT automatically mean developer access is gated.
- OAuth does NOT automatically imply self-serve access.
- OAuth also does NOT automatically imply gated access.

ACCESS MODEL RULE:

Use "Self-serve" ONLY when the supplied evidence explicitly
supports developer access/credential acquisition without requiring
sales contact, partnership approval, admin approval, or an
unestablished paid-plan requirement.

Use "Gated" ONLY when the supplied evidence explicitly indicates
a payment gate, enterprise gate, admin approval, partnership,
contact-sales requirement, or similar access barrier.

Otherwise use "Unknown".

MCP RULE:

- Use "Official" ONLY when the supplied evidence explicitly
  identifies an official MCP implementation/server/support from
  the application or its official developer resources.
- Use "Community" only for clearly identified third-party/community
  MCP implementations.
- If MCP evidence is absent or merely discusses MCP conceptually,
  use "Unknown".
- Do NOT infer MCP availability from API documentation.

BUILDABILITY RULE:

Use "Needs verification" when the evidence does not establish
enough information to make a reliable buildability decision.

EVIDENCE RULE:

Every important classification must be supported by at least one
source.

Return evidence_refs using only the SOURCE NUMBERS that directly
support the result.

Do NOT reproduce evidence text.
Do NOT reproduce URLs.

CONFIDENCE RULE:

Use:
- High = strong, direct, mostly official evidence
- Medium = useful evidence but some ambiguity
- Low = weak, conflicting, or incomplete evidence

Return ONLY valid JSON matching the schema.
No Markdown.
No explanation outside the JSON.

EVIDENCE:

{evidence_text}
""".strip()


# ============================================================
# QWEN ANALYSIS
# ============================================================

def analyze_with_qwen(
    app: str,
    category: str,
    evidence: list[dict],
) -> AppResearch:

    if not evidence:
        raise RuntimeError(
            f"No evidence was collected for {app}."
        )

    prompt = build_prompt(
        app=app,
        category=category,
        evidence=evidence,
    )

    print(
        "\nSending evidence to Qwen3 8B..."
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
            "num_ctx": 8192,
        },
    )

    elapsed = time.time() - start

    print(
        f"Qwen completed in {elapsed:.1f}s"
    )

    # --------------------------------------------------------
    # DIAGNOSTICS
    # --------------------------------------------------------

    try:

        prompt_tokens = response.get(
            "prompt_eval_count"
        )

        prompt_s = (
            response.get(
                "prompt_eval_duration"
            ) or 0
        ) / 1e9

        output_tokens = response.get(
            "eval_count"
        )

        output_s = (
            response.get(
                "eval_duration"
            ) or 0
        ) / 1e9

        tokens_per_second = (
            output_tokens / output_s
            if output_s
            else 0
        )

        thinking = (
            response["message"]
            .get("thinking")
            or ""
        ).strip()

        print(
            f"  prefill: {prompt_tokens} tok "
            f"in {prompt_s:.1f}s | "
            f"decode: {output_tokens} tok "
            f"in {output_s:.1f}s "
            f"({tokens_per_second:.1f} tok/s)"
        )

        print(
            "  thinking:",
            "ACTIVE"
            if thinking
            else "DISABLED",
        )

    except Exception as error:

        print(
            f"  Diagnostics unavailable: "
            f"{error}"
        )

    # --------------------------------------------------------
    # JSON PARSE
    # --------------------------------------------------------

    raw_output = response[
        "message"
    ]["content"]

    print(
        "\n=== RAW QWEN OUTPUT ==="
    )

    print(raw_output)

    try:

        data = json.loads(
            raw_output
        )

    except json.JSONDecodeError as error:

        raise RuntimeError(
            f"Qwen returned invalid JSON: "
            f"{error}"
        ) from error

    # --------------------------------------------------------
    # PYDANTIC VALIDATION
    # --------------------------------------------------------

    try:

        validated = (
            AppResearch.model_validate(
                data
            )
        )

    except Exception as error:

        print(
            "\n=== VALIDATION ERROR ==="
        )

        print(error)

        raise RuntimeError(
            "Qwen output failed "
            "Pydantic validation."
        ) from error

    return validated


# ============================================================
# ATTACH ACTUAL EVIDENCE
# ============================================================

def attach_evidence(
    result: AppResearch,
    evidence: list[dict],
) -> dict:
    """
    Convert Qwen evidence references back into full
    evidence objects for the final dataset.
    """

    evidence_map = {
        item["id"]: {
            "title": item["title"],
            "url": item["url"],
            "evidence_text": item[
                "evidence_text"
            ],
        }
        for item in evidence
    }

    selected_evidence = []

    invalid_refs = []

    for ref in result.evidence_refs:

        if ref in evidence_map:

            selected_evidence.append(
                evidence_map[ref]
            )

        else:

            invalid_refs.append(ref)

    if invalid_refs:

        raise RuntimeError(
            "Qwen returned invalid "
            f"evidence references: "
            f"{invalid_refs}"
        )

    final_result = (
        result.model_dump()
    )

    final_result.pop(
        "evidence_refs",
        None,
    )

    final_result["evidence"] = (
        selected_evidence
    )

    return final_result


# ============================================================
# SAVE RESULT
# ============================================================

def save_result(result: dict) -> None:

    RESULTS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing_results = []

    if RESULTS_FILE.exists():

        try:

            with open(
                RESULTS_FILE,
                "r",
                encoding="utf-8",
            ) as file:

                existing_results = (
                    json.load(file)
                )

                if not isinstance(
                    existing_results,
                    list,
                ):
                    existing_results = []

        except (
            json.JSONDecodeError,
            OSError,
        ):

            existing_results = []

    existing_results = [
        item
        for item in existing_results
        if item.get("app")
        != result.get("app")
    ]

    existing_results.append(
        result
    )

    with open(
        RESULTS_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            existing_results,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"\nSaved result → "
        f"{RESULTS_FILE}"
    )


# ============================================================
# END-TO-END PIPELINE
# ============================================================

def research_app(
    app: str,
    category: str,
):

    overall_start = time.time()

    evidence = (
        collect_evidence(app)
    )

    result = (
        analyze_with_qwen(
            app=app,
            category=category,
            evidence=evidence,
        )
    )

    final_result = (
        attach_evidence(
            result=result,
            evidence=evidence,
        )
    )

    save_result(
        final_result
    )

    total_time = (
        time.time()
        - overall_start
    )

    print(
        "\n"
        + "=" * 60
    )

    print(
        "FINAL VALIDATED RESULT"
    )

    print(
        "=" * 60
    )

    print(
        json.dumps(
            final_result,
            indent=2,
            ensure_ascii=False,
        )
    )

    print(
        f"\nTotal pipeline time: "
        f"{total_time:.1f}s"
    )

    return final_result


# ============================================================
# FIRST END-TO-END TEST
# ============================================================

if __name__ == "__main__":

    research_app(
        app="Salesforce",
        category="CRM",
    )