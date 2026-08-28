import json
import shlex
import subprocess
from pathlib import Path

from fastapi import HTTPException

from api_v04 import app


SANDBOX_HOST = "openshell-knowledge-agent"
SANDBOX_PROJECT = "~/knowledge-agent"
HOST_VISION_DIR = Path.home() / "knowledge-vision"


def newest_manifest():
    search_roots = [
        Path.home(),
        HOST_VISION_DIR,
        Path.home() / "research-knowledge",
    ]

    candidates = []

    for root in search_roots:
        if not root.exists():
            continue

        candidates.extend(
            root.glob("*.package.json")
        )

    candidates = sorted(
        set(candidates),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not candidates:
        raise RuntimeError(
            "No *.package.json manifest found"
        )

    return candidates[0]


def load_manifest(path: Path):
    with path.open(
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


def extract_verified_files(manifest):
    """
    Supports a few reasonable manifest layouts without
    assuming a single exact key name.
    """

    possible_keys = [
        "verified_files",
        "slides",
        "files",
        "verified",
    ]

    values = None

    for key in possible_keys:
        if key in manifest:
            values = manifest[key]
            break

    if values is None:
        raise RuntimeError(
            "Could not find verified slide files in manifest"
        )

    result = []

    for item in values:
        if isinstance(item, str):
            path = item

        elif isinstance(item, dict):
            path = (
                item.get("verified_json")
                or item.get("verified")
                or item.get("sandbox_path")
                or item.get("path")
                or item.get("file")
            )

        else:
            path = None

        if not path:
            continue

        # pipeline.py runs inside the sandbox, so ensure
        # we're passing sandbox-visible verified JSONs.
        if ".verified.json" in path:
            p = Path(path)

            if p.is_absolute():
                sandbox_path = path
            else:
                sandbox_path = (
                    "~/knowledge-agent/data/processed/"
                    + p.name
                )

            result.append(sandbox_path)

    if not result:
        raise RuntimeError(
            "Manifest contains no usable verified JSON files"
        )

    return result


def run_sandbox_pipeline(
    title: str,
    note: str,
):
    manifest_path = newest_manifest()
    manifest = load_manifest(
        manifest_path
    )

    verified_files = extract_verified_files(
        manifest
    )

    quoted_title = shlex.quote(title)
    quoted_note = shlex.quote(note)

    slide_args = " ".join(
        shlex.quote(path)
        for path in verified_files
    )

    command = (
        f"cd {SANDBOX_PROJECT} && "
        f"python3 pipeline.py "
        f"--title {quoted_title} "
        f"--slides {slide_args} "
        f"--note {quoted_note}"
    )

    process = subprocess.run(
        [
            "ssh",
            SANDBOX_HOST,
            command,
        ],
        capture_output=True,
        text=True,
        timeout=1800,
    )

    if process.returncode != 0:
        raise RuntimeError(
            "Sandbox pipeline failed\n"
            f"STDOUT:\n{process.stdout}\n"
            f"STDERR:\n{process.stderr}"
        )

    return {
        "manifest": str(manifest_path),
        "verified_files": verified_files,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


@app.post("/finalize-latest")
def finalize_latest(
    title: str,
    note: str = "",
):
    try:
        result = run_sandbox_pipeline(
            title=title,
            note=note,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    return {
        "ok": True,
        "stage": "knowledge_finalized",
        "title": title,
        "sandbox_pipeline": result,
    }
