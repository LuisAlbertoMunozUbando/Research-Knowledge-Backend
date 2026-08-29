import json
import re
import shlex
import subprocess
import unicodedata
from pathlib import Path

from api_v06 import (
    SANDBOX_HOST,
    run_ssh,
    run_visual_pipeline,
    upload_verified_json,
)

PDF_PYTHON = "/sandbox/.openclaw-data/venvs/pdf-tools/bin/python"
SANDBOX_PROJECT = "/sandbox/knowledge-agent"
SANDBOX_PROCESSED = f"{SANDBOX_PROJECT}/data/processed"
SANDBOX_RAW = f"{SANDBOX_PROJECT}/data/raw"


def _native_text_quality(inspection: dict) -> dict:
    """Estimate whether native PDF text is usable for semantic indexing."""
    texts = [
        str(page.get("text") or "")
        for page in inspection.get("pages", [])
    ]
    text = "\n".join(texts)

    if not text:
        return {
            "usable": False,
            "control_ratio": 1.0,
            "latin_word_chars_ratio": 0.0,
            "reason": "no-native-text",
        }

    total = max(len(text), 1)
    control = sum(
        1
        for ch in text
        if unicodedata.category(ch).startswith("C")
        and ch not in "\n\r\t"
    )

    alpha_chars = sum(1 for ch in text if ch.isalpha())
    latin_words = re.findall(r"[A-Za-z]{3,}", text)
    latin_word_chars = sum(len(word) for word in latin_words)

    control_ratio = control / total
    latin_word_chars_ratio = (
        latin_word_chars / max(alpha_chars, 1)
    )

    # Ordinary born-digital papers are effectively free of embedded
    # control characters. Legacy PDFs with broken font encodings often
    # contain many C0/C1 characters and produce unusable token streams.
    usable = (
        control_ratio <= 0.01
        and latin_word_chars_ratio >= 0.45
    )

    reason = (
        "native-text-usable"
        if usable
        else "native-text-low-quality"
    )

    return {
        "usable": usable,
        "control_ratio": round(control_ratio, 4),
        "latin_word_chars_ratio": round(latin_word_chars_ratio, 4),
        "reason": reason,
    }


def _read_remote_json(path: str) -> dict:
    result = run_ssh(
        "cat " + shlex.quote(path),
        timeout=120,
        label="read remote PDF JSON",
    )
    return json.loads(result["stdout"])


def _render_selected_pages(
    remote_pdf: str,
    package_token: str,
    resource_index: int,
    page_count: int,
):
    wanted = sorted({
        1,
        2,
        max(1, page_count - 3),
        max(1, page_count - 2),
        max(1, page_count - 1),
        max(1, page_count),
    })

    prefix = f"{package_token}_pdf_{resource_index:03d}"

    script = f'''
import json
import pymupdf
from pathlib import Path

pdf = Path({remote_pdf!r})
outdir = Path({SANDBOX_PROCESSED!r})
doc = pymupdf.open(pdf)
wanted = {wanted!r}
created = []

for page_number in wanted:
    if page_number < 1 or page_number > len(doc):
        continue
    page = doc[page_number - 1]
    pix = page.get_pixmap(
        matrix=pymupdf.Matrix(1.7, 1.7),
        alpha=False,
    )
    out = outdir / f"{prefix}_page_{{page_number:03d}}.png"
    pix.save(out)
    created.append({{"page": page_number, "path": str(out)}})

doc.close()
print(json.dumps(created))
'''

    result = run_ssh(
        f"{shlex.quote(PDF_PYTHON)} -c {shlex.quote(script)}",
        timeout=600,
        label="render low-quality PDF pages",
    )

    lines = [line.strip() for line in result["stdout"].splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("PDF visual fallback rendered no pages")

    return json.loads(lines[-1])


def _download_remote_binary(remote_path: str, local_path: Path):
    result = subprocess.run(
        [
            "ssh",
            SANDBOX_HOST,
            "cat " + shlex.quote(remote_path),
        ],
        capture_output=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Could not retrieve rendered PDF page: "
            + result.stderr.decode("utf-8", errors="replace")
        )

    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(result.stdout)


def _unique_strings(values):
    output = []
    for value in values:
        if isinstance(value, str):
            value = value.strip()
            if value and value not in output:
                output.append(value)
    return output


def _merge_verified(base: dict, visuals: list, pages: list, quality: dict) -> dict:
    merged = dict(base)

    summaries = []
    if isinstance(base.get("summary"), str) and base["summary"].strip():
        summaries.append(base["summary"].strip())

    for item in visuals:
        summary = item.get("summary")
        if isinstance(summary, str) and summary.strip():
            summaries.append(summary.strip())

    merged["summary"] = "\n\n".join(_unique_strings(summaries))[:12000]

    array_fields = [
        "detected_topics",
        "people",
        "organizations",
        "projects",
        "concepts",
        "metrics",
        "links_visible",
        "links_mentioned",
        "uncertain_fields",
    ]

    for field in array_fields:
        values = []
        base_values = base.get(field, [])
        if isinstance(base_values, list):
            values.extend(base_values)
        for item in visuals:
            item_values = item.get(field, [])
            if isinstance(item_values, list):
                values.extend(item_values)
        merged[field] = _unique_strings(values)

    # Prefer a meaningful document title from the native PDF pipeline,
    # but use a visual title when the native one is missing/untitled.
    title = str(base.get("title") or "").strip()
    if not title or title.lower() in {"untitled", "unknown"}:
        for item in visuals:
            candidate = str(item.get("title") or "").strip()
            if candidate:
                title = candidate
                break
    merged["title"] = title
    merged["source_type"] = "pdf"

    pdf_details = dict(base.get("pdf_details") or {})
    pdf_details["visual_fallback"] = {
        "activated": True,
        "reason": quality.get("reason"),
        "control_ratio": quality.get("control_ratio"),
        "latin_word_chars_ratio": quality.get("latin_word_chars_ratio"),
        "pages": pages,
        "method": "rendered-pages-plus-Qwen2.5-VL",
    }
    merged["pdf_details"] = pdf_details

    return merged


def run_pdf_with_visual_fallback(
    base_pipeline,
    pdf_path,
    package_token,
    index,
):
    """Run native PDF extraction and add vision evidence only when needed."""
    pdf_path = Path(pdf_path)

    base_result = base_pipeline(
        pdf_path,
        package_token,
        index,
    )

    inspection_path = base_result.get("inspection_json")
    verified_path = base_result.get("verified_json")

    if not inspection_path or not verified_path:
        return base_result

    inspection = _read_remote_json(inspection_path)
    quality = _native_text_quality(inspection)

    base_result["native_text_quality"] = quality

    if quality["usable"]:
        base_result["visual_fallback"] = False
        return base_result

    page_count = int(inspection.get("page_count") or 0)
    suffix = pdf_path.suffix.lower() or ".pdf"
    remote_pdf = (
        f"{SANDBOX_RAW}/"
        f"{package_token}_pdf_{index:03d}{suffix}"
    )

    rendered = _render_selected_pages(
        remote_pdf,
        package_token,
        index,
        page_count,
    )

    local_render_dir = (
        pdf_path.parent
        / f".{pdf_path.stem}_visual_pages"
    )

    visual_verified = []
    page_numbers = []

    for rendered_page in rendered:
        page_number = int(rendered_page["page"])
        remote_image = rendered_page["path"]
        local_image = (
            local_render_dir
            / f"page_{page_number:03d}.png"
        )

        _download_remote_binary(
            remote_image,
            local_image,
        )

        visual_result = run_visual_pipeline(local_image)
        visual_data = json.loads(
            Path(visual_result["verified_json"]).read_text(
                encoding="utf-8"
            )
        )
        visual_data["source_pdf_page"] = page_number
        visual_verified.append(visual_data)
        page_numbers.append(page_number)

    base_verified = _read_remote_json(verified_path)
    merged = _merge_verified(
        base_verified,
        visual_verified,
        page_numbers,
        quality,
    )

    merged_local = (
        pdf_path.parent
        / f"{pdf_path.stem}.multimodal.verified.json"
    )
    merged_local.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    uploaded = upload_verified_json(
        merged_local,
        package_token,
        index,
    )

    base_result["verified_json"] = uploaded["sandbox"]
    base_result["visual_fallback"] = True
    base_result["visual_pages"] = page_numbers
    base_result["merged_verified_json"] = uploaded["sandbox"]

    return base_result
