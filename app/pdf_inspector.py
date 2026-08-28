#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path

import pymupdf


TEXT_THRESHOLD = 120
DIGITAL_RATIO_THRESHOLD = 0.70
SCANNED_RATIO_THRESHOLD = 0.20
MAX_TEXT_PER_PAGE = 5000


def clean_text(text: str) -> str:
    text = text or ""
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def inspect_pdf(path: Path) -> dict:
    doc = pymupdf.open(path)

    pages = []
    total_chars = 0
    total_images = 0
    significant_pages = 0

    for index, page in enumerate(doc, start=1):
        text = clean_text(page.get_text("text"))
        chars = len(text)

        rect = page.rect
        width = float(rect.width)
        height = float(rect.height)
        area = max(width * height, 1.0)
        density = chars / area

        images = page.get_images(full=True)
        image_count = len(images)

        significant_text = chars >= TEXT_THRESHOLD

        if significant_text:
            significant_pages += 1

        total_chars += chars
        total_images += image_count

        pages.append({
            "page": index,
            "chars": chars,
            "width": width,
            "height": height,
            "text_density": density,
            "image_count": image_count,
            "significant_text": significant_text,
            "text": text[:MAX_TEXT_PER_PAGE],
        })

    page_count = len(pages)
    ratio = (
        significant_pages / page_count
        if page_count
        else 0.0
    )

    if ratio >= DIGITAL_RATIO_THRESHOLD:
        classification = "born-digital"
    elif ratio <= SCANNED_RATIO_THRESHOLD:
        classification = "scanned"
    else:
        classification = "hybrid"

    metadata = dict(doc.metadata or {})
    doc.close()

    return {
        "resource_type": "pdf",
        "source": {
            "filename": path.name,
            "path": str(path),
        },
        "classification": classification,
        "page_count": page_count,
        "digital_page_ratio": ratio,
        "statistics": {
            "total_chars": total_chars,
            "average_chars_per_page": (
                total_chars / page_count
                if page_count
                else 0.0
            ),
            "total_images": total_images,
            "pages_with_significant_text": significant_pages,
        },
        "metadata": metadata,
        "pages": pages,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = Path(args.pdf).resolve()
    output = Path(args.output)

    if not source.exists():
        raise FileNotFoundError(source)

    result = inspect_pdf(source)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("PDF INSPECTION CREATED")
    print("classification:", result["classification"])
    print("page_count:", result["page_count"])
    print("digital_page_ratio:", result["digital_page_ratio"])
    print("output:", output)


if __name__ == "__main__":
    main()
