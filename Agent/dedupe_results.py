import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_FILE = PROJECT_ROOT / "data" / "results.json"
BACKUP_FILE = PROJECT_ROOT / "data" / "results.before_dedupe.json"


def canonical_name(value: str) -> str:
    return " ".join(
        value.strip().casefold().split()
    )


def evidence_score(record: dict) -> tuple:
    evidence = record.get("evidence") or []

    # Prefer records with more evidence, then higher confidence.
    confidence_rank = {
        "High": 3,
        "Medium": 2,
        "Low": 1,
    }

    return (
        len(evidence),
        confidence_rank.get(
            record.get("confidence"),
            0,
        ),
    )


def main():
    with open(
        RESULTS_FILE,
        "r",
        encoding="utf-8",
    ) as f:
        records = json.load(f)

    if not isinstance(records, list):
        raise ValueError(
            "results.json must contain a JSON list."
        )

    # Safety backup.
    with open(
        BACKUP_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            records,
            f,
            indent=2,
            ensure_ascii=False,
        )

    grouped = {}

    for record in records:
        app = record.get("app", "")

        if not app:
            raise ValueError(
                "Found result without an app name."
            )

        key = canonical_name(app)

        existing = grouped.get(key)

        if existing is None:
            grouped[key] = record
            continue

        # Keep the stronger record.
        if evidence_score(record) > evidence_score(existing):
            grouped[key] = record

    cleaned = list(grouped.values())

    # Stable ordering.
    cleaned.sort(
        key=lambda r: canonical_name(
            r.get("app", "")
        )
    )

    with open(
        RESULTS_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            cleaned,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print("=" * 68)
    print("RESULT DEDUPLICATION")
    print("=" * 68)
    print(f"Before: {len(records)}")
    print(f"After:  {len(cleaned)}")
    print(
        f"Removed: {len(records) - len(cleaned)}"
    )
    print(
        f"Backup: {BACKUP_FILE}"
    )
    print("=" * 68)

    if len(cleaned) != 100:
        raise RuntimeError(
            f"Expected exactly 100 unique apps, "
            f"got {len(cleaned)}."
        )

    print("✓ Exactly 100 unique app results.")


if __name__ == "__main__":
    main()