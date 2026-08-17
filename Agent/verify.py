from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = PROJECT_ROOT / "data" / "normalized_results.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "verification_queue.json"

TARGET_SAMPLE_SIZE = 20
RANDOM_SEED = 42


# ============================================================
# FILE HELPERS
# ============================================================

def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(
            f"Required file does not exist:\n{path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = path.with_suffix(".tmp")

    with temporary_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

    temporary_file.replace(path)


# ============================================================
# CANONICAL HELPERS
# ============================================================

def app_key(record: dict) -> str:
    return (
        str(record.get("app", ""))
        .strip()
        .casefold()
    )


def evidence_count(record: dict) -> int:
    return len(
        record.get("evidence") or []
    )


# ============================================================
# RISK SCORING
# ============================================================

def calculate_risk(
    record: dict,
) -> tuple[int, list[str]]:
    """
    Calculate how valuable a record is to manually verify.

    Higher score means:
        "This record is more likely to teach us something
         about weaknesses in the research pipeline."

    This is a sampling heuristic, NOT an accuracy claim.
    """

    score = 0
    reasons: list[str] = []

    access_model = record.get(
        "access_model",
        "Unknown",
    )

    buildability = record.get(
        "buildability",
        "Unknown",
    )

    mcp_status = record.get(
        "mcp_status",
        "Unknown",
    )

    confidence = record.get(
        "confidence",
        "Unknown",
    )

    auth_methods = (
        record.get(
            "auth_methods_normalized"
        )
        or record.get(
            "auth_methods"
        )
        or []
    )

    # --------------------------------------------------------
    # ACCESS MODEL
    # --------------------------------------------------------

    if access_model == "Unknown":
        score += 3
        reasons.append(
            "unknown_access_model"
        )

    # --------------------------------------------------------
    # BUILDABILITY
    # --------------------------------------------------------

    if buildability == "Needs verification":
        score += 4
        reasons.append(
            "buildability_needs_verification"
        )

    elif buildability == "Partially buildable":
        score += 2
        reasons.append(
            "partially_buildable"
        )

    # --------------------------------------------------------
    # MCP
    # --------------------------------------------------------

    if mcp_status == "Unknown":
        score += 2
        reasons.append(
            "unknown_mcp_status"
        )

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    if confidence == "Low":
        score += 3
        reasons.append(
            "low_confidence"
        )

    elif confidence == "Unknown":
        score += 2
        reasons.append(
            "unknown_confidence"
        )

    elif confidence == "Medium":
        score += 1
        reasons.append(
            "medium_confidence"
        )

    # --------------------------------------------------------
    # EVIDENCE
    # --------------------------------------------------------

    count = evidence_count(record)

    if count == 0:
        score += 5
        reasons.append(
            "no_evidence"
        )

    elif count <= 2:
        score += 4
        reasons.append(
            f"limited_evidence_{count}_sources"
        )

    elif count == 3:
        score += 2
        reasons.append(
            "moderate_evidence"
        )

    # --------------------------------------------------------
    # AUTHENTICATION COMPLEXITY
    # --------------------------------------------------------

    if len(auth_methods) >= 2:
        score += 1
        reasons.append(
            "multiple_auth_methods"
        )

    # --------------------------------------------------------
    # UNUSUAL AUTHENTICATION
    # --------------------------------------------------------

    common_auth = {
        "oauth",
        "api key",
        "token",
    }

    for method in auth_methods:

        if str(method).casefold() not in common_auth:
            score += 2
            reasons.append(
                f"unusual_auth_{method}"
            )
            break

    # --------------------------------------------------------
    # COMPOUND UNCERTAINTY
    # --------------------------------------------------------

    uncertainty_signals = sum(
        [
            access_model == "Unknown",
            buildability == "Needs verification",
            mcp_status == "Unknown",
            confidence in {"Low", "Unknown"},
        ]
    )

    if uncertainty_signals >= 3:
        score += 3
        reasons.append(
            "multiple_uncertainty_signals"
        )

    return score, reasons


# ============================================================
# CATEGORY GROUPING
# ============================================================

def group_by_category(
    records: list[dict],
) -> dict[str, list[dict]]:

    groups: dict[str, list[dict]] = {}

    for record in records:

        category = str(
            record.get(
                "category",
                "Unknown",
            )
        ).strip()

        groups.setdefault(
            category,
            [],
        ).append(record)

    return groups


# ============================================================
# CANDIDATE SELECTION
# ============================================================

def select_sample(
    records: list[dict],
    target_size: int,
) -> list[dict]:
    """
    Build a deterministic verification sample.

    Strategy:

    1. Select one high-risk record from each category.
    2. Fill remaining slots with globally highest-risk
       records.
    3. Use deterministic alphabetical tie-breaking.

    This provides broad category coverage while concentrating
    additional verification effort on uncertain records.
    """

    if target_size <= 0:
        raise ValueError(
            "target_size must be positive."
        )

    categories = group_by_category(
        records
    )

    selected: dict[str, dict] = {}

    # --------------------------------------------------------
    # PHASE 1
    # One candidate per category.
    # --------------------------------------------------------

    for category in sorted(
        categories,
        key=str.casefold,
    ):

        candidates = categories[
            category
        ]

        ranked = sorted(
            candidates,
            key=lambda record: (
                -calculate_risk(record)[0],
                app_key(record),
            ),
        )

        if not ranked:
            continue

        candidate = ranked[0]

        selected[
            app_key(candidate)
        ] = candidate

    # --------------------------------------------------------
    # PHASE 2
    # Fill remaining slots globally.
    # --------------------------------------------------------

    remaining = [
        record
        for record in records
        if app_key(record)
        not in selected
    ]

    remaining.sort(
        key=lambda record: (
            -calculate_risk(record)[0],
            app_key(record),
        )
    )

    for record in remaining:

        if len(selected) >= target_size:
            break

        selected[
            app_key(record)
        ] = record

    # --------------------------------------------------------
    # FINAL ORDER
    # --------------------------------------------------------

    sample = list(
        selected.values()
    )

    sample.sort(
        key=lambda record: (
            -calculate_risk(record)[0],
            app_key(record),
        )
    )

    return sample[:target_size]


# ============================================================
# BUILD HUMAN VERIFICATION RECORD
# ============================================================

def build_verification_record(
    record: dict,
    position: int,
) -> dict:

    risk, reasons = calculate_risk(
        record
    )

    if risk >= 8:
        priority = "HIGH"

    elif risk >= 4:
        priority = "MEDIUM"

    else:
        priority = "STANDARD"

    evidence = record.get(
        "evidence"
    ) or []

    return {
        "verification_id": (
            f"V{position:02d}"
        ),

        "app": record.get(
            "app"
        ),

        "category": record.get(
            "category"
        ),

        "priority": priority,

        "risk_score": risk,

        "selection_reasons": reasons,

        # ----------------------------------------------------
        # EXACT CLAIMS GENERATED BY THE AGENT
        # ----------------------------------------------------

        "agent_claim": {
            "description": record.get(
                "description"
            ),

            "auth_methods": (
                record.get(
                    "auth_methods_normalized"
                )
                or record.get(
                    "auth_methods",
                    [],
                )
            ),

            "access_model": record.get(
                "access_model"
            ),

            "access_reason": record.get(
                "access_reason"
            ),

            "api_surface": record.get(
                "api_surface"
            ),

            "mcp_status": record.get(
                "mcp_status"
            ),

            "buildability": record.get(
                "buildability"
            ),

            "blocker": record.get(
                "blocker"
            ),

            "confidence": record.get(
                "confidence"
            ),
        },

        # ----------------------------------------------------
        # EVIDENCE THE AGENT USED
        # ----------------------------------------------------

        "evidence": [
            {
                "title": item.get(
                    "title"
                ),

                "url": item.get(
                    "url"
                ),

                "evidence_text": item.get(
                    "evidence_text"
                ),
            }
            for item in evidence
        ],

        # ----------------------------------------------------
        # HUMAN VERIFICATION
        #
        # These remain blank until we actually inspect
        # the source and decide whether the claim is correct.
        # ----------------------------------------------------

        "verification": {
            "status": "PENDING",

            "auth_correct": None,

            "access_correct": None,

            "api_surface_correct": None,

            "mcp_correct": None,

            "buildability_correct": None,

            "overall_result": None,

            "corrected_fields": [],

            "corrected_values": {},

            "verified_source_urls": [],

            "notes": "",
        },
    }


# ============================================================
# VALIDATION
# ============================================================

def validate_dataset(
    records: list[dict],
) -> None:

    if not isinstance(
        records,
        list,
    ):
        raise ValueError(
            "normalized_results.json must contain a JSON list."
        )

    if len(records) != 100:
        raise ValueError(
            f"Expected exactly 100 records; "
            f"found {len(records)}."
        )

    names = [
        app_key(record)
        for record in records
    ]

    duplicates = [
        name
        for name, count in Counter(
            names
        ).items()
        if count > 1
    ]

    if duplicates:
        raise ValueError(
            "Duplicate app names detected: "
            + ", ".join(duplicates)
        )

    missing_names = [
        index
        for index, record in enumerate(
            records
        )
        if not app_key(record)
    ]

    if missing_names:
        raise ValueError(
            "Records missing app names at indexes: "
            + ", ".join(
                map(
                    str,
                    missing_names,
                )
            )
        )


# ============================================================
# REPORTING
# ============================================================

def print_summary(
    queue: list[dict],
) -> None:

    priorities = Counter(
        item["priority"]
        for item in queue
    )

    categories = Counter(
        item["category"]
        for item in queue
    )

    reasons = Counter()

    for item in queue:

        for reason in item.get(
            "selection_reasons",
            [],
        ):
            reasons[reason] += 1

    print()
    print("=" * 72)
    print("VERIFICATION QUEUE")
    print("=" * 72)

    print(
        f"Sample size: {len(queue)}"
    )

    print()
    print("PRIORITY")

    for priority, count in (
        priorities.most_common()
    ):
        print(
            f"  {priority}: {count}"
        )

    print()
    print("CATEGORY COVERAGE")

    for category, count in sorted(
        categories.items()
    ):
        print(
            f"  {category}: {count}"
        )

    print()
    print("TOP SELECTION REASONS")

    for reason, count in (
        reasons.most_common(12)
    ):
        print(
            f"  {reason}: {count}"
        )

    print()
    print("SELECTED APPS")

    for item in queue:

        print(
            f"  {item['verification_id']} "
            f"{item['app']} "
            f"[{item['priority']}] "
            f"risk={item['risk_score']}"
        )

    print("=" * 72)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print()
    print("=" * 72)
    print("AI PRODUCT OPS — VERIFICATION SAMPLER")
    print("=" * 72)

    records = load_json(
        INPUT_FILE
    )

    validate_dataset(
        records
    )

    print(
        f"Input records: {len(records)}"
    )

    print(
        f"Target verification sample: "
        f"{TARGET_SAMPLE_SIZE}"
    )

    sample = select_sample(
        records,
        TARGET_SAMPLE_SIZE,
    )

    if len(sample) != TARGET_SAMPLE_SIZE:
        raise RuntimeError(
            f"Expected {TARGET_SAMPLE_SIZE} "
            f"selected records; got {len(sample)}."
        )

    queue = [
        build_verification_record(
            record,
            index + 1,
        )
        for index, record in enumerate(
            sample
        )
    ]

    document = {
        "metadata": {
            "source": str(
                INPUT_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),

            "total_apps": len(records),

            "sample_size": len(queue),

            "random_seed": RANDOM_SEED,

            "selection_method": (
                "Category-stratified, risk-prioritized "
                "deterministic sampling."
            ),

            "status": (
                "PENDING_HUMAN_VERIFICATION"
            ),
        },

        "instructions": [
            (
                "Open the cited evidence source."
            ),
            (
                "Check each agent claim against the "
                "source rather than relying on plausibility."
            ),
            (
                "Mark each field PASS or FAIL."
            ),
            (
                "For incorrect fields, record the corrected "
                "value and source URL."
            ),
            (
                "Use official documentation whenever "
                "available."
            ),
            (
                "Do not mark a claim verified unless it is "
                "supported by the cited evidence."
            ),
        ],

        "records": queue,
    }

    save_json(
        OUTPUT_FILE,
        document,
    )

    print_summary(
        queue
    )

    print()
    print(
        f"Saved → {OUTPUT_FILE}"
    )
    print()
    print(
        "STATUS: PENDING HUMAN VERIFICATION"
    )
    print(
        "No claims have been marked as verified."
    )
    print("=" * 72)


if __name__ == "__main__":
    main()