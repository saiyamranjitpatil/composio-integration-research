import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RESULTS_FILE = PROJECT_ROOT / "data" / "results.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "analysis.json"


# ============================================================
# HELPERS
# ============================================================

def load_results() -> list[dict]:
    if not RESULTS_FILE.exists():
        raise FileNotFoundError(
            f"Results file not found: {RESULTS_FILE}"
        )

    with open(
        RESULTS_FILE,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(
            "results.json must contain a JSON list."
        )

    return data


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    with open(
        temp_path,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )

    temp_path.replace(path)


def percentage(count: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0

    return round(
        (count / denominator) * 100,
        1,
    )


def sorted_counter(
    counter: Counter,
) -> dict[str, int]:
    return dict(
        sorted(
            counter.items(),
            key=lambda item: (-item[1], item[0]),
        )
    )


# ============================================================
# DATA QUALITY
# ============================================================

def assess_record_quality(record: dict) -> dict:
    """
    Assess whether the record has enough material to be
    considered useful for downstream analysis.

    This does NOT change the record.
    """

    evidence = record.get("evidence") or []

    issues = []

    if not evidence:
        issues.append("no_evidence")

    elif len(evidence) < 3:
        issues.append("low_evidence_count")

    if record.get("access_model") == "Unknown":
        issues.append("unknown_access_model")

    if record.get("mcp_status") == "Unknown":
        issues.append("unknown_mcp_status")

    if record.get("buildability") == "Needs verification":
        issues.append("buildability_needs_verification")

    if record.get("confidence") == "Low":
        issues.append("low_confidence")

    # Check whether evidence URLs are actually present.
    urls = [
        item.get("url")
        for item in evidence
        if item.get("url")
    ]

    if not urls:
        issues.append("no_evidence_urls")

    return {
        "issues": issues,
        "quality": (
            "high"
            if not issues
            else (
                "medium"
                if len(issues) <= 2
                else "low"
            )
        ),
    }


# ============================================================
# MAIN ANALYSIS
# ============================================================

def build_analysis(results: list[dict]) -> dict:
    total = len(results)

    # ----------------------------------------
    # Overall counters
    # ----------------------------------------

    access_counter = Counter()
    buildability_counter = Counter()
    mcp_counter = Counter()
    confidence_counter = Counter()

    auth_counter = Counter()
    category_counter = Counter()

    # ----------------------------------------
    # Lists
    # ----------------------------------------

    gated_apps = []
    buildable_apps = []
    partial_apps = []
    blocked_apps = []
    verification_apps = []
    unknown_access_apps = []

    low_quality_apps = []

    # ----------------------------------------
    # Category stats
    # ----------------------------------------

    category_stats = defaultdict(
        lambda: {
            "apps": 0,
            "access": Counter(),
            "buildability": Counter(),
            "mcp": Counter(),
            "auth": Counter(),
            "needs_verification": 0,
        }
    )

    # ----------------------------------------
    # Evidence statistics
    # ----------------------------------------

    total_evidence_records = 0
    evidence_counts = []

    # ----------------------------------------
    # Process rows
    # ----------------------------------------

    for record in results:

        app = record.get(
            "app",
            "Unknown",
        )

        category = record.get(
            "category",
            "Unknown",
        )

        category_counter[category] += 1

        # ------------------------------
        # Evidence
        # ------------------------------

        evidence = record.get(
            "evidence"
        ) or []

        evidence_count = len(evidence)

        total_evidence_records += evidence_count
        evidence_counts.append(
            evidence_count
        )

        quality = assess_record_quality(
            record
        )

        if quality["quality"] != "high":
            low_quality_apps.append({
                "app": app,
                "quality": quality["quality"],
                "issues": quality["issues"],
                "evidence_count": evidence_count,
            })

        # ------------------------------
        # Auth
        # ------------------------------

        auth_methods = (
            record.get("auth_methods")
            or []
        )

        if not auth_methods:
            auth_counter["Unknown"] += 1
        else:
            for method in auth_methods:
                auth_counter[method] += 1

        # ------------------------------
        # Access
        # ------------------------------

        access_model = record.get(
            "access_model",
            "Unknown",
        )

        access_counter[
            access_model
        ] += 1

        if access_model == "Gated":
            gated_apps.append(app)

        elif access_model == "Unknown":
            unknown_access_apps.append(app)

        # ------------------------------
        # Buildability
        # ------------------------------

        buildability = record.get(
            "buildability",
            "Unknown",
        )

        buildability_counter[
            buildability
        ] += 1

        if buildability == "Buildable today":
            buildable_apps.append(app)

        elif buildability == "Partially buildable":
            partial_apps.append(app)

        elif buildability == "Blocked":
            blocked_apps.append(app)

        elif buildability == "Needs verification":
            verification_apps.append(app)

        # ------------------------------
        # MCP
        # ------------------------------

        mcp_status = record.get(
            "mcp_status",
            "Unknown",
        )

        mcp_counter[
            mcp_status
        ] += 1

        # ------------------------------
        # Confidence
        # ------------------------------

        confidence = record.get(
            "confidence",
            "Unknown",
        )

        confidence_counter[
            confidence
        ] += 1

        # ------------------------------
        # Category aggregation
        # ------------------------------

        stats = category_stats[
            category
        ]

        stats["apps"] += 1
        stats["access"][
            access_model
        ] += 1
        stats["buildability"][
            buildability
        ] += 1
        stats["mcp"][
            mcp_status
        ] += 1

        if not auth_methods:
            stats["auth"]["Unknown"] += 1
        else:
            for method in auth_methods:
                stats["auth"][method] += 1

        if (
            buildability
            == "Needs verification"
        ):
            stats[
                "needs_verification"
            ] += 1

    # ========================================================
    # CATEGORY OUTPUT
    # ========================================================

    category_output = {}

    for category, stats in sorted(
        category_stats.items()
    ):
        apps = stats["apps"]

        category_output[category] = {
            "apps": apps,

            "access": sorted_counter(
                stats["access"]
            ),

            "access_percent": {
                key: percentage(
                    value,
                    apps,
                )
                for key, value
                in stats["access"].items()
            },

            "buildability": sorted_counter(
                stats["buildability"]
            ),

            "buildability_percent": {
                key: percentage(
                    value,
                    apps,
                )
                for key, value
                in stats[
                    "buildability"
                ].items()
            },

            "mcp": sorted_counter(
                stats["mcp"]
            ),

            "auth": sorted_counter(
                stats["auth"]
            ),

            "needs_verification": (
                stats[
                    "needs_verification"
                ]
            ),

            "needs_verification_percent": (
                percentage(
                    stats[
                        "needs_verification"
                    ],
                    apps,
                )
            ),
        }

    # ========================================================
    # OVERALL PERCENTAGES
    # ========================================================

    overall = {
        "access_model": (
            sorted_counter(
                access_counter
            )
        ),

        "access_model_percent": {
            key: percentage(
                value,
                total,
            )
            for key, value
            in access_counter.items()
        },

        "buildability": (
            sorted_counter(
                buildability_counter
            )
        ),

        "buildability_percent": {
            key: percentage(
                value,
                total,
            )
            for key, value
            in buildability_counter.items()
        },

        "mcp_status": (
            sorted_counter(
                mcp_counter
            )
        ),

        "mcp_percent": {
            key: percentage(
                value,
                total,
            )
            for key, value
            in mcp_counter.items()
        },

        "confidence": (
            sorted_counter(
                confidence_counter
            )
        ),

        "authentication": (
            sorted_counter(
                auth_counter
            )
        ),
    }

    # ========================================================
    # QUALITY / COVERAGE
    # ========================================================

    avg_evidence = (
        round(
            total_evidence_records / total,
            2,
        )
        if total
        else 0
    )

    min_evidence = (
        min(evidence_counts)
        if evidence_counts
        else 0
    )

    max_evidence = (
        max(evidence_counts)
        if evidence_counts
        else 0
    )

    high_quality_count = sum(
        1
        for item in results
        if assess_record_quality(item)[
            "quality"
        ] == "high"
    )

    quality_summary = {
        "apps_with_evidence": sum(
            1
            for item in results
            if item.get("evidence")
        ),

        "high_quality_rows": high_quality_count,

        "high_quality_percent": percentage(
            high_quality_count,
            total,
        ),

        "average_evidence_per_app": avg_evidence,
        "minimum_evidence_per_app": min_evidence,
        "maximum_evidence_per_app": max_evidence,

        "apps_with_low_quality_flags": len(
            low_quality_apps
        ),
    }

    # ========================================================
    # RANKED LISTS
    # ========================================================

    # Most common buildability blockers.
    blocker_counter = Counter()

    for record in results:
        blocker = (
            record.get("blocker")
            or ""
        ).strip()

        if blocker:
            blocker_counter[blocker] += 1

    # ========================================================
    # OUTPUT
    # ========================================================

    analysis = {
        "metadata": {
            "completed_apps": total,
            "target_apps": 100,
            "completion_percent": percentage(
                total,
                100,
            ),
            "ready_for_final_analysis": (
                total >= 100
            ),
        },

        "overall": overall,

        "quality": quality_summary,

        "categories": category_output,

        "headline_candidates": {
            "top_auth": (
                auth_counter.most_common(
                    3
                )
            ),

            "top_access_models": (
                access_counter.most_common(
                    3
                )
            ),

            "top_buildability": (
                buildability_counter.most_common(
                    4
                )
            ),

            "top_mcp_status": (
                mcp_counter.most_common(
                    4
                )
            ),

            "top_blockers": (
                blocker_counter.most_common(
                    10
                )
            ),
        },

        "lists": {
            "buildable_today": sorted(
                buildable_apps,
                key=str.lower,
            ),

            "partially_buildable": sorted(
                partial_apps,
                key=str.lower,
            ),

            "blocked": sorted(
                blocked_apps,
                key=str.lower,
            ),

            "needs_verification": sorted(
                verification_apps,
                key=str.lower,
            ),

            "gated": sorted(
                gated_apps,
                key=str.lower,
            ),

            "unknown_access": sorted(
                unknown_access_apps,
                key=str.lower,
            ),

            "low_quality": sorted(
                low_quality_apps,
                key=lambda item: item[
                    "app"
                ].lower(),
            ),
        },
    }

    return analysis


# ============================================================
# TERMINAL SUMMARY
# ============================================================

def print_summary(
    analysis: dict
) -> None:

    metadata = analysis[
        "metadata"
    ]

    overall = analysis[
        "overall"
    ]

    quality = analysis[
        "quality"
    ]

    print("\n" + "=" * 72)
    print("AI PRODUCT OPS — RESEARCH ANALYSIS")
    print("=" * 72)

    print(
        f"Coverage: "
        f"{metadata['completed_apps']}/"
        f"{metadata['target_apps']} "
        f"({metadata['completion_percent']}%)"
    )

    print(
        f"Evidence: "
        f"{quality['apps_with_evidence']} apps | "
        f"{quality['average_evidence_per_app']} "
        f"sources/app"
    )

    print("\nACCESS MODEL")
    for key, value in (
        overall[
            "access_model"
        ].items()
    ):
        pct = overall[
            "access_model_percent"
        ][key]

        print(
            f"  {key}: "
            f"{value} ({pct}%)"
        )

    print("\nBUILDABILITY")
    for key, value in (
        overall[
            "buildability"
        ].items()
    ):
        pct = overall[
            "buildability_percent"
        ][key]

        print(
            f"  {key}: "
            f"{value} ({pct}%)"
        )

    print("\nMCP")
    for key, value in (
        overall[
            "mcp_status"
        ].items()
    ):
        pct = overall[
            "mcp_percent"
        ][key]

        print(
            f"  {key}: "
            f"{value} ({pct}%)"
        )

    print("\nAUTHENTICATION")
    for key, value in (
        overall[
            "authentication"
        ].items()
    ):
        print(
            f"  {key}: {value}"
        )

    print("\nQUALITY FLAGS")
    print(
        f"  High-quality rows: "
        f"{quality['high_quality_rows']}/"
        f"{metadata['completed_apps']}"
    )

    print(
        f"  Needs verification: "
        f"{len(analysis['lists']['needs_verification'])}"
    )

    print(
        f"  Low-quality rows: "
        f"{quality['apps_with_low_quality_flags']}"
    )

    print("\n" + "=" * 72)
    print(
        f"Saved → {OUTPUT_FILE}"
    )
    print("=" * 72)


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    results = load_results()

    analysis = build_analysis(
        results
    )

    save_json(
        OUTPUT_FILE,
        analysis,
    )

    print_summary(
        analysis
    )


if __name__ == "__main__":
    main()