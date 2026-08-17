import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

QUEUE_FILE = PROJECT_ROOT / "data" / "verification_queue.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "verification_results.json"


# ============================================================
# HUMAN / DOC VERIFICATION FOR FIRST 10 APPS
# ============================================================
#
# These are the results of the manual documentation cross-check
# we just completed. We keep them separate from the raw research.
#
# Each field is explicitly marked:
#   True  -> supported
#   False -> corrected
#
# corrected_values contains only fields that changed.
# ============================================================

VERIFIED = {
    "pylon": {
        "auth_correct": True,
        "access_correct": True,
        "api_surface_correct": True,
        "mcp_correct": True,
        "buildability_correct": True,
        "overall_result": "PASS",
        "corrected_values": {},
        "notes": "Bearer authentication and admin token creation are supported by Pylon documentation.",
    },

    "slack": {
        "auth_correct": True,
        "access_correct": False,
        "api_surface_correct": True,
        "mcp_correct": True,
        "buildability_correct": False,
        "overall_result": "FAIL",
        "corrected_values": {
            "access_model": "Self-serve",
            "buildability": "Buildable today",
        },
        "notes": "Slack provides OAuth-based app installation and a mature public API surface.",
    },

    "aircall": {
        "auth_correct": True,
        "access_correct": False,
        "api_surface_correct": True,
        "mcp_correct": True,
        "buildability_correct": False,
        "overall_result": "FAIL",
        "corrected_values": {
            "access_model": "Gated",
            "buildability": "Partially buildable",
        },
        "notes": "OAuth integration access involves Aircall's technology-partner pathway.",
    },

    "freshdesk": {
        "auth_correct": False,
        "access_correct": True,
        "api_surface_correct": True,
        "mcp_correct": True,
        "buildability_correct": True,
        "overall_result": "FAIL",
        "corrected_values": {
            "auth_methods": [
                "Basic Auth",
                "API Key",
            ],
        },
        "notes": "The cited Freshdesk documentation supports username/password and personal API key authentication; OAuth was not supported by the cited evidence.",
    },

    "grain": {
        "auth_correct": False,
        "access_correct": True,
        "api_surface_correct": True,
        "mcp_correct": False,
        "buildability_correct": False,
        "overall_result": "FAIL",
        "corrected_values": {
            "auth_methods": [
                "Personal Access Token",
                "Workspace Access Token",
                "OAuth 2.0",
            ],
            "mcp_status": "Official",
            "buildability": "Partially buildable",
        },
        "notes": "Grain documentation supports PAT/workspace token/OAuth2 flows and an official MCP server.",
    },

    "paygent connect": {
        "auth_correct": False,
        "access_correct": True,
        "api_surface_correct": True,
        "mcp_correct": True,
        "buildability_correct": True,
        "overall_result": "FAIL",
        "corrected_values": {
            "auth_methods": [
                "Unknown",
            ],
        },
        "notes": "The supplied evidence did not establish OAuth authentication.",
    },

    "twenty": {
        "auth_correct": False,
        "access_correct": False,
        "api_surface_correct": True,
        "mcp_correct": True,
        "buildability_correct": False,
        "overall_result": "FAIL",
        "corrected_values": {
            "auth_methods": [
                "API Key",
                "OAuth 2.0",
            ],
            "access_model": "Self-serve",
            "buildability": "Buildable today",
        },
        "notes": "Twenty documentation supports API keys and OAuth 2.0 and explicitly presents the developer platform/API as usable directly.",
    },

    "fanbasis": {
        "auth_correct": False,
        "access_correct": True,
        "api_surface_correct": False,
        "mcp_correct": True,
        "buildability_correct": True,
        "overall_result": "FAIL",
        "corrected_values": {
            "auth_methods": [
                "Unknown",
            ],
            "api_surface": "Needs verification",
        },
        "notes": "The cited material was insufficient to establish the agent's OAuth/username-password claim or a trustworthy general API surface.",
    },

    "notion": {
        "auth_correct": True,
        "access_correct": True,
        "api_surface_correct": True,
        "mcp_correct": False,
        "buildability_correct": False,
        "overall_result": "FAIL",
        "corrected_values": {
            "mcp_status": "Official",
            "buildability": "Buildable today",
        },
        "notes": "Notion documents internal-token and OAuth authentication, plus an official hosted MCP server.",
    },

    "mailchimp": {
        "auth_correct": True,
        "access_correct": False,
        "api_surface_correct": True,
        "mcp_correct": True,
        "buildability_correct": False,
        "overall_result": "FAIL",
        "corrected_values": {
            "access_model": "Self-serve",
            "buildability": "Buildable today",
        },
        "notes": "Mailchimp documentation supports self-generated API keys for account users and a public Marketing API.",
    },
}


def main():
    with open(
        QUEUE_FILE,
        "r",
        encoding="utf-8",
    ) as f:
        queue = json.load(f)

    records = queue["records"]

    updated = []

    field_names = [
        "auth_correct",
        "access_correct",
        "api_surface_correct",
        "mcp_correct",
        "buildability_correct",
    ]

    total_checks = 0
    passed_checks = 0

    overall_passes = 0
    overall_fails = 0

    for record in records[:10]:
        key = record["app"].strip().casefold()

        if key not in VERIFIED:
            raise RuntimeError(
                f"No verification result supplied for {record['app']}"
            )

        verification = VERIFIED[key]

        # Copy the record rather than mutating the queue.
        updated_record = dict(record)

        updated_verification = dict(
            record.get("verification", {})
        )

        updated_verification.update({
            "status": "VERIFIED",
            **verification,
            "verified_source_urls": [
                item["url"]
                for item in record.get("evidence", [])
                if item.get("url")
            ],
        })

        updated_record["verification"] = (
            updated_verification
        )

        updated.append(updated_record)

        # Accuracy stats.
        for field in field_names:
            value = verification[field]

            total_checks += 1

            if value:
                passed_checks += 1

        if verification["overall_result"] == "PASS":
            overall_passes += 1
        else:
            overall_fails += 1

    accuracy = (
        round(
            passed_checks / total_checks * 100,
            1,
        )
        if total_checks
        else 0
    )

    output = {
        "metadata": {
            "sample_size": len(updated),
            "field_checks": total_checks,
            "correct_field_checks": passed_checks,
            "field_accuracy_percent": accuracy,
            "overall_passes": overall_passes,
            "overall_fails": overall_fails,
            "status": "VERIFIED_SAMPLE",
        },
        "records": updated,
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            output,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print("\n" + "=" * 68)
    print("VERIFICATION RESULTS")
    print("=" * 68)

    print(
        f"Apps verified: {len(updated)}"
    )

    print(
        f"Field checks: "
        f"{total_checks}"
    )

    print(
        f"Correct field checks: "
        f"{passed_checks}"
    )

    print(
        f"Field-level accuracy: "
        f"{accuracy}%"
    )

    print(
        f"Overall app passes: "
        f"{overall_passes}"
    )

    print(
        f"Overall app failures: "
        f"{overall_fails}"
    )

    print(
        f"\nSaved → {OUTPUT_FILE}"
    )

    print("=" * 68)


if __name__ == "__main__":
    main()