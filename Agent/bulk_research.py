import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tools import web_search, format_search_evidence


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

APPS_FILE = PROJECT_ROOT / "data" / "app.json"
EVIDENCE_FILE = PROJECT_ROOT / "data" / "raw_evidence.json"

MAX_SEARCH_RESULTS = 2
MAX_WORKERS = 6
MAX_SNIPPET_CHARS = 700


# ============================================================
# SEARCH STRATEGY
# ============================================================

def build_queries(app: str) -> list[str]:
    return [
        f"{app} official API authentication developer documentation",
        f"{app} official API access permissions pricing developer",
        f"{app} official MCP Model Context Protocol",
    ]


# ============================================================
# ONE APP
# ============================================================

def research_one_app(app_record: dict) -> dict:
    """
    Collect web evidence for one application.

    No LLM is called here.
    """

    app = app_record["app"]
    category = app_record.get("category", "")

    start = time.time()

    all_results = []
    seen_urls = set()

    queries = build_queries(app)

    for query in queries:

        try:
            results = web_search(
                query,
                max_results=MAX_SEARCH_RESULTS,
            )

        except Exception as error:

            print(
                f"[{app}] search error: {error}"
            )

            results = []

        for result in results:

            url = result.get(
                "url",
                "",
            ).strip()

            if not url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)

            all_results.append({
                "title": result.get(
                    "title",
                    "",
                ),
                "url": url,
                "snippet": result.get(
                    "snippet",
                    "",
                )[:MAX_SNIPPET_CHARS],
            })

    evidence = format_search_evidence(
        all_results
    )

    elapsed = time.time() - start

    print(
        f"[DONE] {app}: "
        f"{len(evidence)} sources "
        f"in {elapsed:.1f}s"
    )

    return {
        "app": app,
        "category": category,
        "evidence": evidence,
        "search_count": len(queries),
        "source_count": len(evidence),
        "elapsed_seconds": round(
            elapsed,
            2,
        ),
    }


# ============================================================
# LOAD APPS
# ============================================================

def load_apps() -> list[dict]:

    if not APPS_FILE.exists():

        raise FileNotFoundError(
            f"Apps file not found: "
            f"{APPS_FILE}"
        )

    with open(
        APPS_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(file)

    # Support either:
    #
    # [
    #   {"app": "...", "category": "..."}
    # ]
    #
    # or:
    #
    # {"apps": [...]}

    if isinstance(data, dict):

        apps = data.get(
            "apps",
            [],
        )

    elif isinstance(data, list):

        apps = data

    else:

        raise ValueError(
            "app.json must contain "
            "a list or an object with "
            "an 'apps' list."
        )

    if not apps:

        raise ValueError(
            "app.json contains no apps."
        )

    return apps


# ============================================================
# SAVE
# ============================================================

def save_results(results: list[dict]) -> None:

    EVIDENCE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        EVIDENCE_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            results,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"\nSaved evidence → "
        f"{EVIDENCE_FILE}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    overall_start = time.time()

    apps = load_apps()

    print(
        "\n"
        + "=" * 60
    )

    print(
        f"BULK EVIDENCE COLLECTION"
    )

    print(
        f"Apps: {len(apps)}"
    )

    print(
        f"Workers: {MAX_WORKERS}"
    )

    print(
        "=" * 60
    )

    results = []

    completed = 0

    # Threading is appropriate here because the workload is
    # network I/O (web searches), not CPU-heavy computation.

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {
            executor.submit(
                research_one_app,
                app_record,
            ): app_record
            for app_record in apps
        }

        for future in as_completed(
            futures
        ):

            app_record = futures[
                future
            ]

            app_name = app_record.get(
                "app",
                "Unknown",
            )

            try:

                result = future.result()

                results.append(
                    result
                )

                completed += 1

                print(
                    f"PROGRESS: "
                    f"{completed}/{len(apps)}"
                )

            except Exception as error:

                print(
                    f"[FAILED] {app_name}: "
                    f"{error}"
                )

                results.append({
                    "app": app_name,
                    "category": app_record.get(
                        "category",
                        "",
                    ),
                    "evidence": [],
                    "search_count": 3,
                    "source_count": 0,
                    "error": str(error),
                })

                completed += 1

    # Keep output deterministic.
    results.sort(
        key=lambda item: item["app"]
    )

    save_results(
        results
    )

    total_time = (
        time.time()
        - overall_start
    )

    successful = sum(
        1
        for item in results
        if item.get(
            "source_count",
            0,
        ) > 0
    )

    total_sources = sum(
        item.get(
            "source_count",
            0,
        )
        for item in results
    )

    print(
        "\n"
        + "=" * 60
    )

    print(
        "BULK COLLECTION COMPLETE"
    )

    print(
        f"Apps processed: "
        f"{len(results)}"
    )

    print(
        f"Apps with evidence: "
        f"{successful}"
    )

    print(
        f"Total sources: "
        f"{total_sources}"
    )

    print(
        f"Wall-clock time: "
        f"{total_time:.1f}s "
        f"({total_time / 60:.1f} min)"
    )

    print(
        "=" * 60
    )


if __name__ == "__main__":
    main()