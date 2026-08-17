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
You are an evidence extraction agent for an app research project.

IMPORTANT:
Use ONLY the evidence provided below.
Do not use your prior knowledge.
Do not guess.
If the evidence is insufficient, return "Unknown" or "Needs verification".

Return ONLY valid JSON.

Use EXACTLY these fields:

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

STRICT VALUES:

access_model MUST be exactly one of:
- "Self-serve"
- "Gated"
- "Unknown"

mcp_status MUST be exactly one of:
- "Official"
- "Community"
- "None found"
- "Unknown"

buildability MUST be exactly one of:
- "Buildable today"
- "Partially buildable"
- "Blocked"
- "Needs verification"

confidence MUST be exactly one of:
- "High"
- "Medium"
- "Low"

IMPORTANT BUILDABILITY RULE:
Do NOT infer that an app is blocked merely because access depends on an
organization edition or permissions.

If the evidence does not establish that the required API access is
unavailable, return "Needs verification".

IMPORTANT EVIDENCE RULE:
Every substantive conclusion must be supported by the supplied evidence.
Do not add facts from your own knowledge.

Evidence:
{evidence}
"""

payload = {
    "model": "qwen3:8b",
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

output = result["response"]

print("\nQWEN OUTPUT:\n")
print(output)

# Also check whether the response is actually valid JSON.
try:
    parsed = json.loads(output)
    print("\nJSON VALIDATION: PASS")
except json.JSONDecodeError as e:
    print("\nJSON VALIDATION: FAIL")
    print(e)