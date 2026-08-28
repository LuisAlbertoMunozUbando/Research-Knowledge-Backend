#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path


REMOTE_ROOT = "knowledge-drive:KnowledgBase"


def safe_name(text: str, max_len: int = 60) -> str:
    text = text.strip()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^A-Za-z0-9À-ÿ._-]+", "", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-_.")[:max_len] or "untitled"


def run(command):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed:\n{' '.join(command)}\n\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    return result.stdout.strip()


def detect_sequence(path: Path, explicit_sequence=None):
    if explicit_sequence is not None:
        return explicit_sequence

    match = re.search(
        r"(?:^|[_-])slide[_-]?(\d+)",
        path.stem,
        flags=re.IGNORECASE
    )

    if match:
        return int(match.group(1))

    return None


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--image", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--keywords", default="")
    parser.add_argument("--date", default="")
    parser.add_argument(
        "--sequence",
        type=int,
        default=None
    )

    args = parser.parse_args()

    image = Path(args.image).expanduser().resolve()

    if not image.exists():
        raise FileNotFoundError(image)

    date = (
        args.date.strip()
        or datetime.now().strftime("%Y-%m-%d")
    )

    keywords = [
        x.strip()
        for x in args.keywords.split(",")
        if x.strip()
    ]

    keyword_slug = safe_name(
        "-".join(keywords[:5]),
        max_len=80
    )

    title_slug = safe_name(args.title)

    suffix = image.suffix.lower() or ".jpg"

    sequence = detect_sequence(
        image,
        args.sequence
    )

    item_suffix = (
        f"__slide_{sequence:03d}"
        if sequence is not None
        else ""
    )

    image_name = (
        f"{date}__"
        f"{title_slug}__"
        f"{keyword_slug}__"
        f"{args.token}"
        f"{item_suffix}"
        f"{suffix}"
    )

    metadata_name = (
        f"{date}__"
        f"{title_slug}__"
        f"{args.token}"
        f"{item_suffix}"
        ".metadata.json"
    )

    work_dir = (
        Path.home()
        / "research-knowledge"
        / "drive_archive"
        / args.token
    )

    work_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    metadata_path = work_dir / metadata_name

    metadata = {
        "package_token": args.token,
        "sequence": sequence,
        "title": args.title,
        "date": date,
        "summary": args.summary,
        "keywords": keywords,
        "original_filename": image.name,
        "drive_image_filename": image_name,
        "archived_at": (
            datetime.now()
            .astimezone()
            .isoformat()
        )
    }

    metadata_path.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    image_remote = (
        f"{REMOTE_ROOT}/{image_name}"
    )

    metadata_remote = (
        f"{REMOTE_ROOT}/{metadata_name}"
    )

    run([
        "rclone",
        "copyto",
        str(image),
        image_remote
    ])

    run([
        "rclone",
        "copyto",
        str(metadata_path),
        metadata_remote
    ])

    print(
        json.dumps(
            {
                "ok": True,
                "image": image_remote,
                "metadata": metadata_remote,
                "sequence": sequence,
                "keywords": keywords,
                "date": date
            },
            indent=2,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
