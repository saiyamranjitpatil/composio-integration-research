import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = PROJECT_ROOT / "data" / "results.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "normalized_results.json"


# ============================================================
# AUTHENTICATION NORMALIZATION
# ============================================================

def normalize_auth_method(method: str) -> str:
    """
    Convert inconsistent LLM labels into a small canonical taxonomy.

    The original raw value is preserved separately.
    """

    raw = method.strip()
    value = raw.casefold()

    # OAuth family
    if "oauth" in value:
        return "OAuth"

    # API-key family
    if (
        "api key" in value
        or "api keys" in value
        or "x-api-key" in value
        or "application key" in value
        or "personal api key" in value
    ):
        return "API Key"

    # Token family
    if (
        "access token" in value
        or "api token" in value
        or "api tokens" in value
        or "personal access token" in value
        or "personal api token" in value
        or "private access token" in value
        or "developer token" in value
        or "bearer token" in value
    ):
        return "Token"

    # Basic authentication
    if (
        "basic auth" in value
        or "basic authentication" in value
    ):
        return "Basic Auth"

    # JWT
    if "jwt" in value:
        return "JWT"

    # IAM / cloud identity
    if value == "iam" or "iam " in value:
        return "IAM"

    # Username / password
    if (
        "username and password" in value
        or "password-based" in value
        or "email and password" in value
    ):
        return "Username / Password"

    # GitHub Apps
    if "github app" in value:
        return "GitHub App"

    # Payment / agentic auth
    if "payment-based" in value:
        return "Payment-based"

    # Other explicit mechanisms
    if "x-signature" in value:
        return "Signature"

    # Preserve an unusual method rather than destroying information.
    cleaned = re.sub(r"\s+", " ", raw).strip()

    return cleaned


# ============================================================
# RECORD NORMALIZATION
# ============================================================

def normalize_record(record: dict) -> dict:
    normalized = dict(record)

    raw_methods = record.get("auth_methods") or []

    canonical_methods = []
    raw_to_canonical = {}

    for method in raw_methods:
        canonical = normalize_auth_method(method)

        raw_to_canonical[method] = canonical

        if canonical not in canonical_methods:
            canonical_methods.append(canonical)

    normalized["auth_methods_raw"] = raw_methods
    normalized["auth_methods_normalized"] = canonical_methods
    normalized["auth_mapping"] = raw_to_canonical

    # --------------------------------------------------------
    # Better quality classification
    # --------------------------------------------------------
    #
    # Unknown is NOT automatically low quality.
    # It can be the correct answer when the evidence is weak.

    evidence = record.get("evidence") or []
    confidence = record.get(
        "confidence",
        "Unknown",
    )
    buildability = record.get(
        "buildability",
        "Unknown",
    )

    quality_flags = []

    if len(evidence) == 0:
        quality_flags.append("no_evidence")
    elif len(evidence) < 3:
        quality_flags.append("limited_evidence")

    if confidence == "Low":
        quality_flags.append("low_confidence")

    if buildability == "Needs verification":
        quality_flags.append(
            "buildability_requires_verification"
        )

    normalized["quality_flags"] = quality_flags

    normalized["research_quality"] = (
        "Needs review"
        if quality_flags
        else "Supported"
    )

    return normalized


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8",
    ) as f:
        records = json.load(f)

    if not isinstance(records, list):
        raise ValueError(
            "results.json must contain a list."
        )

    normalized = [
        normalize_record(record)
        for record in records
    ]

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            normalized,
            f,
            indent=2,
            ensure_ascii=False,
        )

    # --------------------------------------------------------
    # Quick summary
    # --------------------------------------------------------

    auth_counts = {}

    for record in normalized:
        for method in record[
            "auth_methods_normalized"
        ]:
            auth_counts[method] = (
                auth_counts.get(method, 0) + 1
            )

    print("\n" + "=" * 68)
    print("NORMALIZATION COMPLETE")
    print("=" * 68)

    print(
        f"Input records:  {len(records)}"
    )

    print(
        f"Output records: {len(normalized)}"
    )

    print("\nNORMALIZED AUTHENTICATION:")

    for method, count in sorted(
        auth_counts.items(),
        key=lambda x: (-x[1], x[0]),
    ):
        print(
            f"  {method}: {count}"
        )

    needs_review = sum(
        1
        for record in normalized
        if record["research_quality"]
        == "Needs review"
    )

    print(
        f"\nRows needing review: "
        f"{needs_review}"
    )

    print(
        f"\nSaved → {OUTPUT_FILE}"
    )

    print("=" * 68)


if __name__ == "__main__":
    main()