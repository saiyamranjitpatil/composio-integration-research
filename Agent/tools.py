from ddgs import DDGS
import requests
import trafilatura
from pypdf import PdfReader
from io import BytesIO


# ============================================================
# WEB SEARCH
# ============================================================

def web_search(query: str, max_results: int = 2) -> list[dict]:
    """
    Search the web and return a small, focused set of results.

    We deliberately keep the result count low because the
    assignment has 100 apps and we need predictable runtime.
    """

    try:
        with DDGS(timeout=8) as ddgs:
            results = list(
                ddgs.text(
                    query,
                    max_results=max_results,
                )
            )

        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
            if r.get("href")
        ]

    except Exception as e:
        print(f"  Search failed: {e}")
        return []


# ============================================================
# HTML FETCH
# ============================================================

def fetch_page(url: str, timeout: int = 15) -> dict:
    """
    Fetch and extract readable text from an HTML page.

    This is a secondary evidence source. Search snippets remain
    usable when direct page fetching is blocked.
    """

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/139.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
        )

        response.raise_for_status()

        text = trafilatura.extract(
            response.text,
            include_links=True,
            include_tables=True,
        )

        return {
            "success": bool(text),
            "url": response.url,
            "status_code": response.status_code,
            "text": text or "",
            "error": None if text else "No extractable text",
        }

    except requests.RequestException as e:
        response = getattr(e, "response", None)

        return {
            "success": False,
            "url": url,
            "status_code": (
                response.status_code
                if response is not None
                else None
            ),
            "text": "",
            "error": str(e),
        }


# ============================================================
# PDF FETCH
# ============================================================

def fetch_pdf(url: str, timeout: int = 20) -> dict:
    """
    Download and extract text from a PDF.
    """

    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0"},
        )

        response.raise_for_status()

        reader = PdfReader(
            BytesIO(response.content)
        )

        pages = []

        for page in reader.pages:
            text = page.extract_text()

            if text:
                pages.append(text)

        return {
            "success": True,
            "url": url,
            "pages": len(reader.pages),
            "text": "\n\n".join(pages),
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "url": url,
            "pages": 0,
            "text": "",
            "error": str(e),
        }


# ============================================================
# EVIDENCE FORMATTING
# ============================================================

def format_search_evidence(results: list[dict]) -> list[dict]:
    """
    Convert search results into our standard evidence format.
    """

    return [
        {
            "source_type": "search_result",
            "title": result["title"],
            "url": result["url"],
            "evidence_text": result["snippet"],
        }
        for result in results
        if result.get("url")
    ]


# ============================================================
# MANUAL TEST
# ============================================================

if __name__ == "__main__":

    print("\n=== SEARCH TEST ===\n")

    results = web_search(
        "Salesforce official REST API OAuth developer documentation",
        max_results=2,
    )

    for index, result in enumerate(results, start=1):

        print(f"{index}. {result['title']}")
        print(f"   {result['url']}")
        print(f"   {result['snippet'][:300]}")
        print()