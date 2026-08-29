import json
import urllib.request


OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"
REASONING_MODEL = "nemotron-3-nano:30b"

MAX_SUMMARY_CHARS = 6000
MAX_TOPICS = 12
MAX_ORGANIZATIONS = 10
MAX_PROJECTS = 10


def _compact_strings(values, limit):
    if not isinstance(values, list):
        return []

    output = []
    for value in values:
        if not isinstance(value, str):
            continue
        value = value.strip()
        if not value or value in output:
            continue
        output.append(value)
        if len(output) >= limit:
            break
    return output


def ask_nemotron(question, results):
    evidence = []

    for index, item in enumerate(results, start=1):
        summary = str(item.get("summary", "") or "").strip()

        evidence.append({
            "source": index,
            "package_id": item["package_id"],
            "title": str(item.get("title", "") or "").strip(),
            "summary": summary[:MAX_SUMMARY_CHARS],
            "topics": _compact_strings(
                item.get("topics", []),
                MAX_TOPICS,
            ),
            "organizations": _compact_strings(
                item.get("organizations", []),
                MAX_ORGANIZATIONS,
            ),
            "projects": _compact_strings(
                item.get("projects", []),
                MAX_PROJECTS,
            ),
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
        "keep_alive": "5m",
        "options": {
            "temperature": 0,
            "num_ctx": 16384,
            "num_predict": 768,
        },
    }

    request = urllib.request.Request(
        OLLAMA_GENERATE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=600,
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
