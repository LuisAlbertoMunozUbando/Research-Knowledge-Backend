import json
import re
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

DB_PATH = Path.home() / "knowledge-agent" / "data" / "knowledge.db"

TOPIC_MAP = {
    "machinelearning": "Machine Learning",
    "deeplearning": "Deep Learning",
    "opensource": "Open Source",
    "computervision": "Computer Vision",
    "bioinformatics": "Bioinformatics",
    "cuda": "CUDA",
    "cupy": "CuPy",
}

OCR_NOISE_EXACT = {"", "a", "py", "gpuc", "acialling"}
URL_RE = re.compile(r'https?://[^\s\]\)>"]+')


def unique_preserve(values):
    result = []
    seen = set()
    for value in values or []:
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
        key = (
            json.dumps(value, sort_keys=True, ensure_ascii=False)
            if isinstance(value, (dict, list))
            else str(value).casefold()
        )
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def normalize_topic(value):
    value = str(value).strip()
    if not value:
        return None
    compact = re.sub(r"[^a-z0-9]+", "", value.casefold())
    if compact in OCR_NOISE_EXACT:
        return None
    if compact in TOPIC_MAP:
        return TOPIC_MAP[compact]
    if len(value) <= 1:
        return None
    if len(value) <= 3 and value.isalpha():
        return None
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_topics(values):
    return unique_preserve(
        [v for v in (normalize_topic(x) for x in values or []) if v]
    )


def extract_raw_url(value):
    if not value:
        return None
    match = URL_RE.search(str(value).strip())
    if not match:
        return None
    url = match.group(0).rstrip(".,;:")
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
    except Exception:
        return None
    return url


def normalize_links(values):
    return unique_preserve(
        [u for u in (extract_raw_url(v) for v in values or []) if u]
    )


def normalize_string_list(values):
    return unique_preserve([str(v).strip() for v in values or [] if str(v).strip()])


def normalize_metrics(values):
    result = []
    for value in values or []:
        text = str(value).strip()
        if not text:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            continue
        result.append(text)
    return unique_preserve(result)


def normalize_relationships(values):
    result = []
    for value in values or []:
        if isinstance(value, dict):
            cleaned = {
                str(k).strip(): str(v).strip()
                for k, v in value.items()
                if str(v).strip()
            }
            if cleaned:
                result.append(cleaned)
        else:
            text = str(value).strip()
            if text:
                result.append(text)
    return unique_preserve(result)


def canonicalize(synthesis):
    if not isinstance(synthesis, dict):
        raise ValueError("Synthesis must be a JSON object")

    title = str(
        synthesis.get("suggested_title")
        or synthesis.get("title")
        or ""
    ).strip()
    summary = str(
        synthesis.get("package_summary")
        or synthesis.get("summary")
        or ""
    ).strip()

    organizations = normalize_string_list(synthesis.get("organizations", []))
    projects = normalize_string_list(synthesis.get("projects", []))

    # Conservative repair observed in early package synthesis: some organizations
    # were also emitted under projects. Keep the organization classification and
    # remove exact duplicates from projects.
    org_keys = {x.casefold() for x in organizations}
    projects = [x for x in projects if x.casefold() not in org_keys]

    return {
        "title": title,
        "summary": summary,
        "detected_topics": normalize_topics(synthesis.get("detected_topics", [])),
        "people": normalize_string_list(synthesis.get("people", [])),
        "organizations": organizations,
        "projects": projects,
        "concepts": normalize_topics(synthesis.get("concepts", [])),
        "metrics": normalize_metrics(synthesis.get("metrics", [])),
        "links_visible": normalize_links(synthesis.get("links_visible", [])),
        "links_mentioned": normalize_links(synthesis.get("links_mentioned", [])),
        "key_points": normalize_string_list(synthesis.get("key_points", [])),
        "relationships": normalize_relationships(synthesis.get("relationships", [])),
        "uncertainties": normalize_string_list(synthesis.get("uncertainties", [])),
    }


def save_final(package_id, final):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE packages SET package_final=? WHERE id=?",
        (json.dumps(final, ensure_ascii=False), int(package_id)),
    )
    conn.commit()
    conn.close()


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: canonicalize_package.py <package_id>")

    package_id = int(sys.argv[1])
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT package_summary FROM packages WHERE id=?",
        (package_id,),
    ).fetchone()
    conn.close()

    if not row:
        raise SystemExit(f"Package {package_id} not found")
    if not row[0]:
        raise SystemExit(f"Package {package_id} has no package_summary")

    synthesis = json.loads(row[0])
    final = canonicalize(synthesis)
    save_final(package_id, final)
    print(json.dumps(final, indent=2, ensure_ascii=False))
    print("PACKAGE FINAL SAVED")


if __name__ == "__main__":
    main()
