from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = PROJECT_ROOT / "data" / "final_results.json"
VERIFICATION_FILE = (
    PROJECT_ROOT / "data" / "verification_results.json"
)
OUTPUT_FILE = PROJECT_ROOT / "data" / "final_analysis.json"


# ============================================================
# IO
# ============================================================

def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_json(
    path: Path,
    data: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = path.with_suffix(".tmp")

    with temp_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

    temp_path.replace(path)


# ============================================================
# COUNTING
# ============================================================

def count_list_field(
    records: list[dict],
    field: str,
) -> Counter:
    counter = Counter()

    for record in records:
        values = record.get(field) or []

        if not isinstance(values, list):
            values = [values]

        for value in values:
            value = str(value).strip()

            if value:
                counter[value] += 1

    return counter


def count_scalar_field(
    records: list[dict],
    field: str,
) -> Counter:
    counter = Counter()

    for record in records:
        value = str(
            record.get(field) or ""
        ).strip()

        if value:
            counter[value] += 1

    return counter


# ============================================================
# CATEGORY ANALYSIS
# ============================================================

def build_category_analysis(
    records: list[dict],
) -> dict:
    groups = defaultdict(list)

    for record in records:
        category = (
            str(
                record.get(
                    "category",
                    "Unknown",
                )
            )
            .strip()
            .casefold()
        )

        groups[category].append(record)

    output = {}

    for category in sorted(groups):
        apps = groups[category]

        output[category] = {
            "app_count": len(apps),

            "authentication": dict(
                count_list_field(
                    apps,
                    "auth_methods_normalized",
                ).most_common()
            ),

            "access_model": dict(
                count_scalar_field(
                    apps,
                    "access_model",
                ).most_common()
            ),

            "mcp": dict(
                count_scalar_field(
                    apps,
                    "mcp_status",
                ).most_common()
            ),

            "buildability": dict(
                count_scalar_field(
                    apps,
                    "buildability",
                ).most_common()
            ),
        }

    return output


# ============================================================
# VERIFICATION ANALYSIS
# ============================================================

def build_verification_analysis(
    final_metadata: dict,
) -> dict:

    result = {
        "verified_apps": final_metadata.get(
            "verified_apps",
            0,
        ),

        "field_accuracy_percent": None,

        "overall_pass_rate_percent": None,

        "apps_with_corrections": final_metadata.get(
            "apps_with_applied_corrections",
            0,
        ),

        "field_corrections_applied": final_metadata.get(
            "total_applied_field_corrections",
            0,
        ),

        "field_checks": None,

        "correct_field_checks": None,

        "field_corrections": {},
    }

    if not VERIFICATION_FILE.exists():
        return result

    verification_data = load_json(
        VERIFICATION_FILE
    )

    metadata = verification_data.get(
        "metadata",
        {},
    )

    field_checks = metadata.get(
        "field_checks",
        0,
    )

    correct_field_checks = metadata.get(
        "correct_field_checks",
        0,
    )

    sample_size = metadata.get(
        "sample_size",
        final_metadata.get(
            "verified_apps",
            0,
        ),
    )

    overall_passes = metadata.get(
        "overall_passes",
        0,
    )

    result.update({
        "field_checks": field_checks,

        "correct_field_checks": (
            correct_field_checks
        ),

        "field_accuracy_percent": (
            round(
                correct_field_checks
                / field_checks
                * 100,
                1,
            )
            if field_checks
            else None
        ),

        "overall_pass_rate_percent": (
            round(
                overall_passes
                / sample_size
                * 100,
                1,
            )
            if sample_size
            else None
        ),

        "field_corrections": metadata.get(
            "field_corrections",
            {},
        ),
    })

    return result


# ============================================================
# FINDINGS
# ============================================================

def build_findings(
    auth: Counter,
    access: Counter,
    mcp: Counter,
    buildability: Counter,
    verification: dict,
) -> list[dict]:

    total = 100

    oauth_count = sum(
        count
        for method, count in auth.items()
        if "oauth" in method.casefold()
    )

    api_key_count = sum(
        count
        for method, count in auth.items()
        if "api key" in method.casefold()
    )

    official_mcp = mcp.get(
        "Official",
        0,
    )

    community_mcp = mcp.get(
        "Community",
        0,
    )

    unknown_mcp = mcp.get(
        "Unknown",
        0,
    )

    unknown_access = access.get(
        "Unknown",
        0,
    )

    buildable_today = buildability.get(
        "Buildable today",
        0,
    )

    partially_buildable = buildability.get(
        "Partially buildable",
        0,
    )

    needs_verification = buildability.get(
        "Needs verification",
        0,
    )

    return [
        {
            "headline": (
                "OAuth is the dominant authentication pattern."
            ),
            "support": {
                "oauth_app_mentions": oauth_count,
                "dataset_size": total,
            },
            "product_implication": (
                "OAuth should be treated as a first-class "
                "authentication primitive in the integration system."
            ),
        },
        {
            "headline": (
                "API keys are the second major integration pattern."
            ),
            "support": {
                "api_key_app_mentions": api_key_count,
                "dataset_size": total,
            },
            "product_implication": (
                "Credential handling should support secure "
                "static-key authentication alongside OAuth."
            ),
        },
        {
            "headline": (
                "MCP adoption is growing but remains uneven."
            ),
            "support": {
                "official": official_mcp,
                "community": community_mcp,
                "unknown": unknown_mcp,
            },
            "product_implication": (
                "MCP should complement, not replace, "
                "conventional API-based integrations."
            ),
        },
        {
            "headline": (
                "Buildability is fragmented across the portfolio."
            ),
            "support": {
                "buildable_today": buildable_today,
                "partially_buildable": partially_buildable,
                "needs_verification": needs_verification,
            },
            "product_implication": (
                "Integration planning needs an explicit "
                "verification step before promising full buildability."
            ),
        },
        {
            "headline": (
                "Access-model uncertainty is a major research bottleneck."
            ),
            "support": {
                "unknown_access": unknown_access,
                "dataset_size": total,
            },
            "product_implication": (
                "The research workflow should explicitly distinguish "
                "API availability from credential access, permissions, "
                "plan restrictions, and partner gating."
            ),
        },
        {
            "headline": (
                "Human verification materially changed the sample."
            ),
            "support": {
                "verified_apps": verification.get(
                    "verified_apps",
                    0,
                ),
                "field_accuracy_percent": verification.get(
                    "field_accuracy_percent"
                ),
                "apps_with_corrections": verification.get(
                    "apps_with_corrections",
                    0,
                ),
                "field_corrections_applied": verification.get(
                    "field_corrections_applied",
                    0,
                ),
            },
            "product_implication": (
                "A verification loop is necessary before treating "
                "LLM-generated research as production-grade truth."
            ),
        },
    ]


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    data = load_json(
        INPUT_FILE
    )

    if not isinstance(data, dict):
        raise ValueError(
            "final_results.json must contain an object."
        )

    records = data.get(
        "records",
        [],
    )

    final_metadata = data.get(
        "metadata",
        {},
    )

    if len(records) != 100:
        raise ValueError(
            f"Expected exactly 100 records, "
            f"found {len(records)}."
        )

    # --------------------------------------------------------
    # Canonical authentication taxonomy.
    # --------------------------------------------------------

    auth = count_list_field(
        records,
        "auth_methods_normalized",
    )

    # --------------------------------------------------------
    # Overall classifications.
    # --------------------------------------------------------

    access = count_scalar_field(
        records,
        "access_model",
    )

    mcp = count_scalar_field(
        records,
        "mcp_status",
    )

    buildability = count_scalar_field(
        records,
        "buildability",
    )

    verification = (
        build_verification_analysis(
            final_metadata
        )
    )

    result = {
        "metadata": {
            "apps": 100,

            "verified_apps": final_metadata.get(
                "verified_apps",
                0,
            ),

            "unverified_apps": final_metadata.get(
                "unverified_apps",
                100,
            ),

            "apps_with_corrections": final_metadata.get(
                "apps_with_applied_corrections",
                0,
            ),

            "field_corrections_applied": final_metadata.get(
                "total_applied_field_corrections",
                0,
            ),

            "source": "data/final_results.json",
        },

        "overall": {
            "authentication": dict(
                auth.most_common()
            ),

            "access_model": dict(
                access.most_common()
            ),

            "mcp": dict(
                mcp.most_common()
            ),

            "buildability": dict(
                buildability.most_common()
            ),
        },

        "category_analysis": (
            build_category_analysis(
                records
            )
        ),

        "verification": verification,

        "headline_findings": build_findings(
            auth,
            access,
            mcp,
            buildability,
            verification,
        ),
    }

    save_json(
        OUTPUT_FILE,
        result,
    )

    # ========================================================
    # TERMINAL REPORT
    # ========================================================

    print()
    print("=" * 72)
    print("FINAL RESEARCH ANALYSIS")
    print("=" * 72)

    print(
        f"Apps: {len(records)}"
    )

    print()
    print("NORMALIZED AUTHENTICATION")

    for key, value in auth.most_common():
        print(
            f"  {key}: {value}"
        )

    print()
    print("ACCESS MODEL")

    for key, value in access.most_common():
        print(
            f"  {key}: {value}"
        )

    print()
    print("MCP")

    for key, value in mcp.most_common():
        print(
            f"  {key}: {value}"
        )

    print()
    print("BUILDABILITY")

    for key, value in buildability.most_common():
        print(
            f"  {key}: {value}"
        )

    print()
    print("VERIFICATION")

    print(
        f"  Apps verified: "
        f"{verification['verified_apps']}"
    )

    print(
        f"  Field accuracy: "
        f"{verification['field_accuracy_percent']}%"
    )

    print(
        f"  Apps with corrections: "
        f"{verification['apps_with_corrections']}"
    )

    print(
        f"  Field corrections applied: "
        f"{verification['field_corrections_applied']}"
    )

    print()
    print("KEY FINDINGS")

    for index, finding in enumerate(
        result["headline_findings"],
        start=1,
    ):
        print(
            f"  {index}. "
            f"{finding['headline']}"
        )

    print()
    print(
        f"Saved → {OUTPUT_FILE}"
    )

    print("=" * 72)


if __name__ == "__main__":
    main()