import json
import urllib.request


OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"
REASONING_MODEL = "nemotron-3-nano:30b"


def ask_nemotron(question, results):
    evidence = []

    for index, item in enumerate(results, start=1):
        evidence.append({
            "source": index,
            "package_id": item["package_id"],
            "title": item["title"],
            "summary": item.get("summary", ""),
            "topics": item.get("topics", []),
            "organizations": item.get("organizations", []),
            "projects": item.get("projects", [])
        })

    prompt = f"""
You are answering a research question using ONLY the supplied
Research Knowledge Hub evidence.

RULES:
1. Do not use external knowledge.
2. Do not invent facts.
3. If the evidence is insufficient, explicitly say so.
4. Cite package IDs inline using [Package N].
5. Distinguish facts from interpretation.
6. Answer in the same language as the question.
7. Be concise but technically informative.

QUESTION:
{question}

EVIDENCE:
{json.dumps(evidence, ensure_ascii=False, indent=2)}

Return JSON with exactly:
{{
  "answer": "string",
  "source_package_ids": [1, 2],
  "insufficient_evidence": false
}}
"""

    payload = {
        "model": REASONING_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0
        }
    }

    request = urllib.request.Request(
        OLLAMA_GENERATE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=600
    ) as response:
        result = json.loads(
            response.read().decode("utf-8")
        )

    raw = result.get("response", "")

    if not raw:
        raise RuntimeError(
            "Nemotron returned an empty response"
        )

    return json.loads(raw)
