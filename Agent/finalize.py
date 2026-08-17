from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SOURCE_FILE = (
    PROJECT_ROOT
    / "data"
    / "normalized_results.json"
)

VERIFICATION_FILE = (
    PROJECT_ROOT
    / "data"
    / "verification_results.json"
)

RAW_FILE = (
    PROJECT_ROOT
    / "data"
    / "results.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "final_results.json"
)


# ============================================================
# IO
# ============================================================

def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing required file: {path}"
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
# HELPERS
# ============================================================

def canonical_app_name(value: Any) -> str:
    return (
        str(value or "")
        .strip()
        .casefold()
    )


def get_verification_map(
    verification_data: dict,
) -> dict[str, dict]:

    records = verification_data.get(
        "records",
        [],
    )

    verification_map = {}

    for record in records:

        app = canonical_app_name(
            record.get("app")
        )

        if not app:
            continue

        if app in verification_map:
            raise ValueError(
                f"Duplicate verification record: "
                f"{record.get('app')}"
            )

        verification_map[app] = record

    return verification_map


# ============================================================
# APPLY ONE VERIFIED RECORD
# ============================================================

def apply_verification(
    result: dict,
    verification: dict,
) -> tuple[dict, list[str]]:

    final = dict(result)

    verification_block = (
        verification.get("verification")
        or {}
    )

    corrected_values = (
        verification_block.get(
            "corrected_values"
        )
        or {}
    )

    corrected_fields = (
        verification_block.get(
            "corrected_fields"
        )
        or []
    )

    changed_fields: list[str] = []

    # --------------------------------------------------------
    # Apply only explicitly verified corrections.
    # --------------------------------------------------------

    for field, corrected_value in (
        corrected_values.items()
    ):

        # Ignore accidental metadata writes.
        if field.startswith("_"):
            continue

        old_value = final.get(field)

        if old_value != corrected_value:
            final[field] = corrected_value
            changed_fields.append(field)

    # --------------------------------------------------------
    # Preserve verification metadata.
    # --------------------------------------------------------

    final["_verification"] = {
        "status": verification_block.get(
            "status",
            "VERIFIED",
        ),

        "overall_result": verification_block.get(
            "overall_result"
        ),

        "corrected_fields": (
            corrected_fields
        ),

        "verified_source_urls": (
            verification_block.get(
                "verified_source_urls",
                [],
            )
        ),

        "notes": verification_block.get(
            "notes",
            "",
        ),
    }

    final["_verification"]["applied_changes"] = (
        changed_fields
    )

    return final, changed_fields


# ============================================================
# VALIDATION
# ============================================================

def validate_100_apps(
    records: list[dict],
) -> None:

    if len(records) != 100:
        raise ValueError(
            f"Expected exactly 100 final records; "
            f"found {len(records)}."
        )

    keys = [
        canonical_app_name(
            record.get("app")
        )
        for record in records
    ]

    if any(not key for key in keys):
        raise ValueError(
            "At least one result is missing an app name."
        )

    duplicates = {
        key
        for key in keys
        if keys.count(key) > 1
    }

    if duplicates:
        raise ValueError(
            "Duplicate apps in final dataset: "
            + ", ".join(
                sorted(duplicates)
            )
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    normalized = load_json(
        SOURCE_FILE
    )

    verification_data = load_json(
        VERIFICATION_FILE
    )

    # Optional raw-source check.
    raw = load_json(
        RAW_FILE
    )

    if not isinstance(
        normalized,
        list,
    ):
        raise ValueError(
            "normalized_results.json must be a list."
        )

    if not isinstance(
        raw,
        list,
    ):
        raise ValueError(
            "results.json must be a list."
        )

    if len(normalized) != 100:
        raise ValueError(
            "Normalized dataset must contain 100 apps."
        )

    if len(raw) != 100:
        raise ValueError(
            "Raw dataset must contain 100 apps."
        )

    verification_map = (
        get_verification_map(
            verification_data
        )
    )

    final_results = []

    verified_count = 0
    corrected_app_count = 0
    total_field_corrections = 0

    for result in normalized:

        app_key = canonical_app_name(
            result.get("app")
        )

        verification = verification_map.get(
            app_key
        )

        if verification is None:
            # No human verification for this app.
            final = dict(result)

            final["_verification"] = {
                "status": "NOT_SAMPLED",
                "overall_result": None,
                "corrected_fields": [],
                "verified_source_urls": [],
                "notes": "",
                "applied_changes": [],
            }

        else:
            final, changed_fields = (
                apply_verification(
                    result,
                    verification,
                )
            )

            verified_count += 1

            if changed_fields:
                corrected_app_count += 1
                total_field_corrections += (
                    len(changed_fields)
                )

        final_results.append(final)

    # Stable order.
    final_results.sort(
        key=lambda record: canonical_app_name(
            record.get("app")
        )
    )

    validate_100_apps(
        final_results
    )

    # --------------------------------------------------------
    # Dataset metadata
    # --------------------------------------------------------

    document = {
        "metadata": {
            "total_apps": len(final_results),

            "verified_apps": verified_count,

            "unverified_apps": (
                len(final_results)
                - verified_count
            ),

            "apps_with_applied_corrections": (
                corrected_app_count
            ),

            "total_applied_field_corrections": (
                total_field_corrections
            ),

            "source_pipeline": [
                "results.json",
                "normalized_results.json",
                "verification_results.json",
            ],

            "verification_status": (
                "PARTIAL_HUMAN_VERIFICATION"
            ),
        },

        "records": final_results,
    }

    save_json(
        OUTPUT_FILE,
        document,
    )

    # ========================================================
    # TERMINAL REPORT
    # ========================================================

    print("\n" + "=" * 72)
    print("FINAL DATASET")
    print("=" * 72)

    print(
        f"Final records: "
        f"{len(final_results)}"
    )

    print(
        f"Human-verified: "
        f"{verified_count}"
    )

    print(
        f"Not sampled: "
        f"{len(final_results) - verified_count}"
    )

    print(
        f"Apps with corrections: "
        f"{corrected_app_count}"
    )

    print(
        f"Field corrections applied: "
        f"{total_field_corrections}"
    )

    print(
        f"\nSaved → {OUTPUT_FILE}"
    )

    print("=" * 72)


if __name__ == "__main__":
    main()