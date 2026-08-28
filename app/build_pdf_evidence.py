#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path


def compact(text, limit=3500):
    text = text or ""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:limit]


def build_evidence(input_path: Path):
    data = json.loads(
        input_path.read_text(
            encoding="utf-8"
        )
    )

    pages = data.get("pages", [])
    page_count = int(
        data.get("page_count", 0)
    )

    # Current deterministic policy for the stable milestone:
    # first two + last four pages. This intentionally stays
    # simple and reproducible; section-aware selection can be
    # introduced later without changing the downstream contract.
    wanted_pages = {
        1,
        2,
        max(1, page_count - 3),
        max(1, page_count - 2),
        max(1, page_count - 1),
        page_count,
    }

    selected = []

    for page in pages:
        if page.get("page") in wanted_pages:
            selected.append({
                "page": page.get("page"),
                "chars": page.get(
                    "chars",
                    0
                ),
                "image_count": page.get(
                    "image_count",
                    0
                ),
                "text": compact(
                    page.get(
                        "text",
                        ""
                    )
                )
            })

    return {
        "resource_type": "pdf",
        "classification": data.get(
            "classification",
            "unknown"
        ),
        "page_count": page_count,
        "metadata": data.get(
            "metadata",
            {}
        ),
        "statistics": data.get(
            "statistics",
            {}
        ),
        "selected_pages": selected,
        "provenance": {
            "source_filename": (
                data.get(
                    "source",
                    {}
                ).get(
                    "filename",
                    ""
                )
            ),
            "selection_strategy": (
                "first-two-and-last-four-pages"
            )
        }
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "inspection_json"
    )

    parser.add_argument(
        "--output",
        required=True
    )

    args = parser.parse_args()

    src = Path(
        args.inspection_json
    )

    dst = Path(
        args.output
    )

    evidence = build_evidence(src)

    dst.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    dst.write_text(
        json.dumps(
            evidence,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    compact_json = json.dumps(
        evidence,
        ensure_ascii=False,
        separators=(",", ":")
    )

    print("PDF EVIDENCE CREATED")
    print(
        "selected_pages:",
        [
            p["page"]
            for p in evidence[
                "selected_pages"
            ]
        ]
    )
    print(
        "payload_chars:",
        len(compact_json)
    )
    print(
        "output:",
        dst
    )


if __name__ == "__main__":
    main()
