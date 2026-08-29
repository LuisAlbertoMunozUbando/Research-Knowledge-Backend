import json
import re
import urllib.request


OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"
REASONING_MODEL = "nemotron-3-nano:30b"

MAX_SUMMARY_CHARS = 6000
MAX_TOPICS = 12
MAX_ORGANIZATIONS = 10
MAX_PROJECTS = 10


_PACKAGE_CITATION_RE = re.compile(r"\[Package\s+(\d+)\]", re.IGNORECASE)
_PACKAGE_REFERENCE_RE = re.compile(r"\bpackage\s+(\d+)\b", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


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


def _drop_ungrounded_sentences(answer, allowed_ids):
    """Remove whole sentences that reference package IDs outside retrieval."""
    if not answer:
        return ""

    kept = []
    for sentence in _SENTENCE_SPLIT_RE.split(answer.strip()):
        refs = {
            int(match.group(1))
            for match in _PACKAGE_REFERENCE_RE.finditer(sentence)
        }
        if refs and not refs.issubset(allowed_ids):
            continue
        kept.append(sentence.strip())

    return " ".join(part for part in kept if part).strip()


def _ground_result(data, results):
    if not isinstance(data, dict):
        raise ValueError("RAG result must be a JSON object")

    allowed_ids = {
        int(item["package_id"])
        for item in results
        if "package_id" in item
    }

    raw_ids = data.get("source_package_ids", [])
    grounded_ids = []
    if isinstance(raw_ids, list):
        for value in raw_ids:
            try:
                package_id = int(value)
            except (TypeError, ValueError):
                continue
            if package_id in allowed_ids and package_id not in grounded_ids:
                grounded_ids.append(package_id)

    answer = str(data.get("answer", "") or "").strip()

    # If the model mentions an un-retrieved package in ordinary prose such as
    # "package 2", discard the whole sentence instead of merely deleting the
    # number and leaving an unsupported claim behind.
    answer = _drop_ungrounded_sentences(answer, allowed_ids)

    def citation_filter(match):
        package_id = int(match.group(1))
        if package_id in allowed_ids:
            return f"[Package {package_id}]"
        return ""

    answer = _PACKAGE_CITATION_RE.sub(citation_filter, answer)
    answer = re.sub(r"[ \t]{2,}", " ", answer).strip()

    inline_ids = []
    for match in _PACKAGE_REFERENCE_RE.finditer(answer):
        package_id = int(match.group(1))
        if package_id in allowed_ids and package_id not in inline_ids:
            inline_ids.append(package_id)

    # Prefer explicit grounded source IDs from the model; if omitted but the
    # answer contains valid inline package references, derive the IDs from them.
    if not grounded_ids and inline_ids:
        grounded_ids = inline_ids

    insufficient = bool(data.get("insufficient_evidence", False))

    # An answer stripped to nothing is, by definition, insufficient.
    if not answer:
        insufficient = True
        grounded_ids = []

    return {
        "answer": answer,
        "source_package_ids": grounded_ids,
        "insufficient_evidence": insufficient,
    }


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

    allowed_ids = [item["package_id"] for item in results]

    prompt = f"""
You are answering a research question using ONLY the supplied
Research Knowledge Hub evidence.

RULES:
1. Do not use external knowledge.
2. Do not invent facts.
3. If the evidence is insufficient, explicitly say so.
4. Cite package IDs inline using [Package N].
5. You may cite ONLY these package IDs: {allowed_ids}.
6. source_package_ids MUST be a subset of those package IDs.
7. Never mention any other package number, even in ordinary prose.
8. Distinguish facts from interpretation.
9. Answer in the same language as the question.
10. Be concise but technically informative.

QUESTION:
{question}

EVIDENCE:
{json.dumps(evidence, ensure_ascii=False, indent=2)}

Return JSON with exactly:
{{
  "answer": "string",
  "source_package_ids": [],
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

    parsed = json.loads(raw)
    return _ground_result(parsed, results)
