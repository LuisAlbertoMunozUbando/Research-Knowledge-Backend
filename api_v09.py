import shutil
import threading
import uuid
from pathlib import Path
from typing import List

from fastapi import BackgroundTasks, File, Form, HTTPException, UploadFile

from api_v08 import (
    app,
    continue_pipeline,
    is_complete,
    load_state,
    mark_complete,
    mark_failed,
    new_state,
    remove_route,
    UPLOAD_ROOT,
)


# ---------------------------------------------------------
# Replace the synchronous v0.8 upload route
# ---------------------------------------------------------

remove_route("/upload", "POST")


# A single DGX Spark should not run multiple heavy ingestion
# pipelines simultaneously from the same API process.
_PIPELINE_LOCK = threading.Lock()


def process_package_background(package_token: str):
    """Continue a saved package outside the HTTP request lifecycle."""
    try:
        with _PIPELINE_LOCK:
            state = load_state(package_token)

            if is_complete(state, "searchable"):
                return

            continue_pipeline(state)

    except Exception as exc:
        try:
            state = load_state(package_token)
            current = state.get("current_stage")
            mark_failed(
                state,
                "pipeline_after_" + str(current),
                exc,
            )
        except Exception:
            # The original exception is already represented by the
            # interrupted worker. Never crash the API process while
            # trying to persist secondary diagnostic state.
            pass


@app.post("/upload", status_code=202)
async def upload_v09(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    note: str = Form(""),
    files: List[UploadFile] = File(...),
):
    """Persist uploads quickly, return 202, process asynchronously."""
    title = title.strip()
    note = note.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Package title is required",
        )

    if not files:
        raise HTTPException(
            status_code=400,
            detail="At least one file is required",
        )

    allowed_suffixes = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".pdf",
    }

    originals = []
    for index, upload in enumerate(files, start=1):
        original = Path(
            upload.filename or f"resource_{index}.jpg"
        ).name
        suffix = Path(original).suffix.lower()

        if suffix not in allowed_suffixes:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported resource type: "
                    + (suffix or "no extension")
                ),
            )
        originals.append(original)

    package_token = uuid.uuid4().hex[:12]
    package_dir = UPLOAD_ROOT / package_token
    package_dir.mkdir(parents=True, exist_ok=False)

    state = new_state(
        package_token,
        title,
        note,
        originals,
    )

    try:
        saved_files = []

        for index, upload in enumerate(files, start=1):
            original = originals[index - 1]
            suffix = Path(original).suffix.lower()
            destination = (
                package_dir
                / f"slide_{index:03d}{suffix}"
            )

            with destination.open("wb") as output:
                shutil.copyfileobj(upload.file, output)

            saved_files.append(str(destination))

        mark_complete(
            state,
            "saved",
            saved_files=saved_files,
        )

    except Exception as exc:
        mark_failed(
            state,
            "pipeline_after_" + str(state.get("current_stage")),
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Upload could not be persisted",
                "package_token": package_token,
                "error": str(exc),
            },
        )

    background_tasks.add_task(
        process_package_background,
        package_token,
    )

    return {
        "ok": True,
        "accepted": True,
        "stage": "saved",
        "package_token": package_token,
        "title": title,
        "files": originals,
        "state_endpoint": f"/pipeline/{package_token}",
        "message": "Upload accepted. Processing continues on DGX Spark.",
    }


@app.get("/pipeline/{package_token}")
def pipeline_status_v09(package_token: str):
    try:
        state = load_state(package_token)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Pipeline state not found",
        )

    return {
        "ok": True,
        "processing": not is_complete(state, "searchable"),
        **state,
    }


@app.get("/v09/status")
def v09_status():
    return {
        "ok": True,
        "version": "0.9.0",
        "pipeline": "persistent-resumable-async",
        "upload_behavior": "202-accepted-background-processing",
        "state_endpoint": "/pipeline/{package_token}",
        "resume_endpoint": "/resume/{package_token}",
    }
