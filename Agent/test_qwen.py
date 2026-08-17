import json
import urllib.request

evidence = """
Salesforce official developer documentation says:
- Salesforce APIs support OAuth 2.0 for authentication.
- Salesforce provides REST API access.
- Developers can create connected apps and use OAuth for API access.

Salesforce developer documentation also states that some API access depends on the Salesforce edition and permissions of the organization.
"""

prompt = f"""
You are a research extraction agent.

Use ONLY the evidence below. Do not use your prior knowledge.

Return ONLY valid JSON with exactly these fields:

{{
  "app": "Salesforce",
  "auth_methods": [],
  "access_model": "",
  "api_surface": "",
  "mcp_status": "",
  "buildability": "",
  "blocker": "",
  "evidence": [],
  "confidence": ""
}}

Rules:
- Never invent facts.
- If the evidence does not establish something, use "unknown".
- Separate API availability from whether access is self-serve.
- Buildability must be based only on the evidence provided.
- Evidence should contain short statements directly supported by the supplied text.

Evidence:
{evidence}
"""

payload = {
    "model": "qwen2.5:3b",
    "prompt": prompt,
    "stream": False,
    "format": "json"
}

request = urllib.request.Request(
    "http://localhost:11434/api/generate",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

with urllib.request.urlopen(request) as response:
    result = json.loads(response.read().decode())

print(result["response"])