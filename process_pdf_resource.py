#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import uuid
from pathlib import Path


PDF_PYTHON = (
    "/sandbox/.openclaw-data/venvs/"
    "pdf-tools/bin/python"
)

PROJECT = Path(
    "/sandbox/knowledge-agent"
)

PROCESSED = (
    PROJECT
    / "data"
    / "processed"
)

OPENCLAW_CONFIG = (
    "/sandbox/.openclaw-data/"
    "openclaw-agents.json"
)


def run(command, timeout=600, env=None):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Command failed\n\n"
            f"COMMAND:\n{command}\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

    return result


def extract_agent_text(stdout):
    envelope = json.loads(stdout)

    payloads = envelope.get(
        "payloads",
        []
    )

    if not payloads:
        raise ValueError(
            "Agent returned no payload"
        )

    text = payloads[0].get(
        "text",
        ""
    ).strip()

    if not text:
        raise ValueError(
            "Agent payload is empty"
        )

    return text


def extract_agent_payload(stdout):
    return json.loads(
        extract_agent_text(stdout)
    )


def build_retry_prompt(evidence):
    return (
        "Return ONLY valid minified JSON. "
        "No Markdown. No comments. "
        "No trailing commas. "
        "Use only supplied evidence. "
        "If unknown use empty string or array. "
        "Keep output under 1200 words. "
        "Required keys exactly: "
        "title,authors,document_type,"
        "publication_date,doi,abstract,"
        "summary,sections,topics,concepts,"
        "people,organizations,projects,"
        "methods,datasets,experiments,"
        "results,metrics,figures,tables,"
        "references_key,links,provenance,"
        "uncertainties. "
        "All fields except title,"
        "document_type,publication_date,"
        "doi,abstract,summary must be arrays. "
        "Maximum 5 items per array. "
        "Maximum 80 words for abstract and "
        "80 words for summary. "
        "\nEVIDENCE:\n"
        + json.dumps(
            evidence,
            ensure_ascii=False,
            separators=(",", ":")
        )
    )


def build_pdf_prompt(evidence):
    schema = {
        "title": "",
        "authors": [],
        "document_type": "",
        "publication_date": "",
        "doi": "",
        "abstract": "",
        "summary": "",
        "sections": [],
        "topics": [],
        "concepts": [],
        "people": [],
        "organizations": [],
        "projects": [],
        "methods": [],
        "datasets": [],
        "experiments": [],
        "results": [],
        "metrics": [],
        "figures": [],
        "tables": [],
        "references_key": [],
        "links": [],
        "provenance": [],
        "uncertainties": []
    }

    instructions = """
You are a compact PDF research extraction agent.

Return ONLY one valid JSON object.
Never use Markdown or code fences.
Use ONLY the supplied PDF evidence.
Do not invent missing facts.

HARD OUTPUT LIMITS:
- title: one string
- authors: max 8 short strings
- document_type: one short string
- publication_date: one short string
- doi: one string or empty
- abstract: max 120 words
- summary: max 100 words
- sections: max 8 short strings
- topics: max 8 short strings
- concepts: max 8 short strings
- people: max 8 short strings
- organizations: max 6 short strings
- projects: max 6 short strings
- methods: max 6 short strings
- datasets: max 4 short strings
- experiments: max 4 short strings
- results: max 6 short strings
- metrics: max 4 short strings
- figures: max 4 short strings
- tables: max 4 short strings
- references_key: max 5 short strings
- links: max 4 complete http/https URLs
- provenance: max 6 short strings with page numbers
- uncertainties: max 4 short strings

Prefer omission/empty arrays over long explanations.
Keep the entire response compact.
"""

    return (
        instructions
        + "\nREQUIRED JSON KEYS:\n"
        + json.dumps(
            schema,
            ensure_ascii=False,
            separators=(",", ":")
        )
        + "\nPDF EVIDENCE:\n"
        + json.dumps(
            evidence,
            ensure_ascii=False,
            separators=(",", ":")
        )
    )


def deterministic_pdf_fallback(evidence):
    """
    Last-resort normalized evidence.

    This contains no invented information.
    It is produced only from deterministic PDF
    inspection/evidence when the generative
    pdf-researcher cannot return valid JSON.
    """

    metadata = evidence.get(
        "metadata",
        {}
    ) or {}

    selected_pages = evidence.get(
        "selected_pages",
        []
    ) or []

    title = (
        metadata.get("title")
        or ""
    )

    snippets = []

    provenance = []

    for page in selected_pages:
        page_number = page.get(
            "page"
        )

        text = (
            page.get("text")
            or ""
        ).strip()

        if text:
            snippets.append(text)

        if page_number is not None:
            provenance.append(
                f"page {page_number}"
            )

    raw_text = "\n\n".join(
        snippets
    )

    # Keep fallback deliberately compact.
    summary = raw_text[:1800]

    return {
        "title": title,
        "authors": [],
        "document_type": "pdf",
        "publication_date": "",
        "doi": "",
        "abstract": "",
        "summary": summary,
        "sections": [],
        "topics": [],
        "concepts": [],
        "people": [],
        "organizations": [],
        "projects": [],
        "methods": [],
        "datasets": [],
        "experiments": [],
        "results": [],
        "metrics": [],
        "figures": [],
        "tables": [],
        "references_key": [],
        "links": [],
        "provenance": provenance[:6],
        "uncertainties": [
            (
                "pdf-researcher did not return "
                "valid structured JSON; "
                "deterministic PDF evidence "
                "was preserved instead"
            )
        ]
    }


def validate_normalized_pdf(data):
    """
    Enforce a stable full contract regardless
    of what the agent returned.
    """

    if not isinstance(data, dict):
        raise ValueError(
            "Normalized PDF payload "
            "must be a JSON object"
        )

    scalar_keys = {
        "title",
        "document_type",
        "publication_date",
        "doi",
        "abstract",
        "summary",
    }

    array_keys = {
        "authors",
        "sections",
        "topics",
        "concepts",
        "people",
        "organizations",
        "projects",
        "methods",
        "datasets",
        "experiments",
        "results",
        "metrics",
        "figures",
        "tables",
        "references_key",
        "links",
        "provenance",
        "uncertainties",
    }

    normalized = {}

    for key in scalar_keys:
        value = data.get(
            key,
            ""
        )

        normalized[key] = (
            value
            if isinstance(value, str)
            else str(value or "")
        )

    for key in array_keys:
        value = data.get(
            key,
            []
        )

        if not isinstance(
            value,
            list
        ):
            value = [value]

        normalized[key] = [
            item
            for item in value
            if item not in (
                None,
                ""
            )
        ]

    return normalized


def normalize_for_pipeline(
    normalized,
    source_pdf
):
    """
    Adapter from PDF-specific normalized
    evidence to the common verified
    evidence shape consumed downstream.
    """

    topics = normalized.get(
        "topics",
        []
    )

    concepts = normalized.get(
        "concepts",
        []
    )

    people = normalized.get(
        "people",
        []
    )

    authors = normalized.get(
        "authors",
        []
    )

    # Authors are people too, but preserve
    # deduplication deterministically.
    merged_people = []

    for value in authors + people:
        if (
            isinstance(value, str)
            and value.strip()
            and value.strip()
            not in merged_people
        ):
            merged_people.append(
                value.strip()
            )

    links = [
        x.strip()
        for x in normalized.get(
            "links",
            []
        )
        if (
            isinstance(x, str)
            and (
                x.strip().startswith(
                    "http://"
                )
                or x.strip().startswith(
                    "https://"
                )
            )
        )
    ]

    summary_parts = []

    if normalized.get("abstract"):
        summary_parts.append(
            normalized["abstract"]
        )

    if normalized.get("summary"):
        summary_parts.append(
            normalized["summary"]
        )

    summary = "\n\n".join(
        x.strip()
        for x in summary_parts
        if isinstance(x, str)
        and x.strip()
    )

    return {
        "title": normalized.get(
            "title",
            ""
        ),
        "source_type": "pdf",
        "summary": summary[:5000],
        "detected_topics": topics,
        "people": merged_people,
        "organizations": normalized.get(
            "organizations",
            []
        ),
        "projects": normalized.get(
            "projects",
            []
        ),
        "concepts": concepts,
        "metrics": normalized.get(
            "metrics",
            []
        ),
        "links_visible": links,
        "links_mentioned": [],
        "uncertain_fields": normalized.get(
            "uncertainties",
            []
        ),
        "pdf_details": {
            "authors": authors,
            "document_type": (
                normalized.get(
                    "document_type",
                    ""
                )
            ),
            "publication_date": (
                normalized.get(
                    "publication_date",
                    ""
                )
            ),
            "doi": normalized.get(
                "doi",
                ""
            ),
            "sections": normalized.get(
                "sections",
                []
            ),
            "methods": normalized.get(
                "methods",
                []
            ),
            "datasets": normalized.get(
                "datasets",
                []
            ),
            "experiments": normalized.get(
                "experiments",
                []
            ),
            "results": normalized.get(
                "results",
                []
            ),
            "figures": normalized.get(
                "figures",
                []
            ),
            "tables": normalized.get(
                "tables",
                []
            ),
            "references_key": (
                normalized.get(
                    "references_key",
                    []
                )
            ),
            "provenance": normalized.get(
                "provenance",
                []
            )
        },
        "source_pdf": str(
            source_pdf
        )
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "pdf"
    )

    parser.add_argument(
        "--token",
        default=""
    )

    parser.add_argument(
        "--index",
        type=int,
        default=1
    )

    args = parser.parse_args()

    pdf = Path(
        args.pdf
    ).resolve()

    if not pdf.exists():
        raise FileNotFoundError(pdf)

    token = (
        args.token.strip()
        or uuid.uuid4().hex[:12]
    )

    PROCESSED.mkdir(
        parents=True,
        exist_ok=True
    )

    prefix = (
        f"{token}_pdf_{args.index:03d}"
    )

    inspection = (
        PROCESSED
        / f"{prefix}.inspection.json"
    )

    evidence_path = (
        PROCESSED
        / f"{prefix}.evidence.json"
    )

    normalized_path = (
        PROCESSED
        / f"{prefix}.normalized.json"
    )

    verified_path = (
        PROCESSED
        / f"{prefix}.verified.json"
    )

    # 1. Inspect PDF deterministically.
    run([
        PDF_PYTHON,
        str(
            PROJECT
            / "app"
            / "pdf_inspector.py"
        ),
        str(pdf),
        "--output",
        str(inspection)
    ])

    # 2. Compact PDF evidence.
    run([
        "python3",
        str(
            PROJECT
            / "app"
            / "build_pdf_evidence.py"
        ),
        str(inspection),
        "--output",
        str(evidence_path)
    ])

    evidence = json.loads(
        evidence_path.read_text(
            encoding="utf-8"
        )
    )

    # 3. Ask pdf-researcher.
    prompt = build_pdf_prompt(
        evidence
    )

    env = dict(os.environ)
    env[
        "OPENCLAW_CONFIG_PATH"
    ] = OPENCLAW_CONFIG

    result = run(
        [
            "openclaw",
            "agent",
            "--local",
            "--agent",
            "pdf-researcher",
            "--json",
            "--thinking",
            "off",
            "--timeout",
            "600",
            "--session-id",
            str(uuid.uuid4()),
            "-m",
            prompt
        ],
        timeout=660,
        env=env
    )

    raw_path = (
        PROCESSED
        / f"{prefix}.agent.raw.json"
    )

    raw_path.write_text(
        result.stdout,
        encoding="utf-8"
    )

    try:
        normalized = (
            extract_agent_payload(
                result.stdout
            )
        )

        normalized = (
            validate_normalized_pdf(
                normalized
            )
        )

    except (
        json.JSONDecodeError,
        ValueError
    ):
        retry_prompt = (
            build_retry_prompt(
                evidence
            )
        )

        retry_result = run(
            [
                "openclaw",
                "agent",
                "--local",
                "--agent",
                "pdf-researcher",
                "--json",
                "--thinking",
                "off",
                "--timeout",
                "600",
                "--session-id",
                str(uuid.uuid4()),
                "-m",
                retry_prompt
            ],
            timeout=660,
            env=env
        )

        retry_raw_path = (
            PROCESSED
            / (
                f"{prefix}."
                "agent.retry.raw.json"
            )
        )

        retry_raw_path.write_text(
            retry_result.stdout,
            encoding="utf-8"
        )

        try:
            normalized = (
                extract_agent_payload(
                    retry_result.stdout
                )
            )

            normalized = (
                validate_normalized_pdf(
                    normalized
                )
            )

        except (
            json.JSONDecodeError,
            ValueError
        ):
            # Generative extraction is useful,
            # but never allowed to block
            # ingestion permanently.
            normalized = (
                deterministic_pdf_fallback(
                    evidence
                )
            )

    normalized_path.write_text(
        json.dumps(
            normalized,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    # 4. Adapt to common evidence contract.
    verified = (
        normalize_for_pipeline(
            normalized,
            pdf
        )
    )

    verified_path.write_text(
        json.dumps(
            verified,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "ok": True,
                "resource_type": "pdf",
                "token": token,
                "inspection_json": (
                    str(inspection)
                ),
                "evidence_json": (
                    str(evidence_path)
                ),
                "normalized_json": (
                    str(normalized_path)
                ),
                "verified_json": (
                    str(verified_path)
                )
            },
            indent=2,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
