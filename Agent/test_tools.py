from tools import web_search, fetch_page


print("\n=== WEB SEARCH TEST ===\n")

results = web_search(
    "Salesforce official developer API documentation OAuth REST API",
    max_results=5,
)

for i, result in enumerate(results, 1):
    print(f"{i}. {result['title']}")
    print(f"   {result['url']}")
    print(f"   {result['snippet'][:300]}")
    print()


print("\n=== PAGE FETCH TEST ===\n")

if results:
    url = results[0]["url"]

    try:
        page = fetch_page(url)

        print("URL:", page["url"])
        print("Extracted characters:", len(page["text"]))
        print("\nFirst 1000 characters:\n")
        print(page["text"][:1000])

    except Exception as e:
        print("FETCH ERROR:", e)