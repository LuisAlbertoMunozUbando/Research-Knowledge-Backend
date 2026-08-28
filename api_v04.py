import shutil
import subprocess
import uuid
from pathlib import Path
from typing import List

from fastapi import File, Form, HTTPException, UploadFile

from api_v03 import app


UPLOAD_ROOT = (
    Path.home()
    / "research-knowledge"
    / "uploads"
)

PIPELINE_HOST = (
    Path.home()
    / "knowledge-vision"
    / "pipeline_host.py"
)

UPLOAD_ROOT.mkdir(
    parents=True,
    exist_ok=True
)


@app.post("/upload")
async def upload_knowledge(
    title: str = Form(...),
    note: str = Form(""),
    files: List[UploadFile] = File(...)
):
    title = title.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Package title is required"
        )

    if not files:
        raise HTTPException(
            status_code=400,
            detail="At least one image is required"
        )

    if not PIPELINE_HOST.exists():
        raise HTTPException(
            status_code=500,
            detail=f"pipeline_host.py not found at {PIPELINE_HOST}"
        )

    package_token = uuid.uuid4().hex[:12]

    package_dir = (
        UPLOAD_ROOT
        / package_token
    )

    package_dir.mkdir(
        parents=True,
        exist_ok=False
    )

    saved_files = []

    for index, upload in enumerate(
        files,
        start=1
    ):
        original_name = (
            Path(upload.filename or f"slide{index}.jpg")
            .name
        )

        suffix = (
            Path(original_name).suffix.lower()
            or ".jpg"
        )

        destination = (
            package_dir
            / f"slide_{index:03d}{suffix}"
        )

        with destination.open("wb") as output:
            shutil.copyfileobj(
                upload.file,
                output
            )

        saved_files.append(destination)

    command = [
        "python3",
        str(PIPELINE_HOST),
        "--title",
        title,
        "--slides",
        *[
            str(path)
            for path in saved_files
        ],
    ]

    try:
        process = subprocess.run(
            command,
            cwd=str(
                Path.home()
                / "knowledge-vision"
            ),
            capture_output=True,
            text=True,
            timeout=1800
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Vision pipeline timed out"
        )

    if process.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Vision pipeline failed",
                "stdout": process.stdout,
                "stderr": process.stderr,
            }
        )

    return {
        "ok": True,
        "package_token": package_token,
        "title": title,
        "note": note,
        "slides": len(saved_files),
        "files": [
            path.name
            for path in saved_files
        ],
        "pipeline_stdout": process.stdout,
        "pipeline_stderr": process.stderr,
        "stage": "vision_verified"
    }
