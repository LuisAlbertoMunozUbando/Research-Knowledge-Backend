import json
import os
import re
import shlex
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import List

from fastapi import File, Form, HTTPException, UploadFile

from api_v05 import app

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

HOME = Path.home()

RESEARCH_DIR = HOME / "research-knowledge"
UPLOAD_ROOT = RESEARCH_DIR / "uploads"
HOST_DB = RESEARCH_DIR / "data" / "knowledge.db"

VISION_DIR = HOME / "knowledge-vision"
EMBEDDING_HOST = VISION_DIR / "embedding_host.py"

SANDBOX_HOST = "openshell-knowledge-agent"
SANDBOX_NAME = "knowledge-agent"
SANDBOX_PROJECT = "~/knowledge-agent"

SANDBOX_PROCESSED = (
    "/sandbox/knowledge-agent/data/processed"
)

SANDBOX_EMBEDDING_DIR = (
    "/sandbox/knowledge-agent/data/embedding_jobs"
)

SANDBOX_DB = (
    "/sandbox/knowledge-agent/data/knowledge.db"
)

SANDBOX_SNAPSHOT = (
    "/sandbox/knowledge-agent/data/knowledge.snapshot.db"
)

UPLOAD_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

HOST_DB.parent.mkdir(
    parents=True,
    exist_ok=True
)


# ---------------------------------------------------------
# REMOVE OLD EXPERIMENTAL ROUTES
# ---------------------------------------------------------

def remove_route(path: str, method: str):
    kept = []

    for route in app.router.routes:
        route_path = getattr(
            route,
            "path",
            None
        )

        route_methods = getattr(
            route,
            "methods",
            set()
        ) or set()

        if (
            route_path == path
            and method.upper() in route_methods
        ):
            continue

        kept.append(route)

    app.router.routes = kept


# Replace the old upload implementation.
remove_route(
    "/upload",
    "POST"
)

# finalize-latest was useful for development,
# but should no longer be part of normal v06 workflow.
remove_route(
    "/finalize-latest",
    "POST"
)


# ---------------------------------------------------------
# COMMAND HELPERS
# ---------------------------------------------------------

def run_command(
    command,
    *,
    cwd=None,
    timeout=1800,
    label="command"
):
    started = time.time()

    process = subprocess.run(
        [str(x) for x in command],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout
    )

    elapsed = round(
        time.time() - started,
        2
    )

    if process.returncode != 0:
        raise RuntimeError(
            f"{label} failed\n\n"
            f"COMMAND:\n"
            f"{' '.join(str(x) for x in command)}\n\n"
            f"STDOUT:\n"
            f"{process.stdout}\n\n"
            f"STDERR:\n"
            f"{process.stderr}"
        )

    return {
        "stdout": process.stdout,
        "stderr": process.stderr,
        "seconds": elapsed
    }


def run_ssh(
    command: str,
    *,
    timeout=1800,
    label="sandbox command"
):
    return run_command(
        [
            "ssh",
            SANDBOX_HOST,
            command
        ],
        timeout=timeout,
        label=label
    )


# ---------------------------------------------------------
# VISION
# ---------------------------------------------------------

def run_visual_pipeline(
    image: Path
):
    visual_json = image.with_suffix(
        ".visual.json"
    )

    verified_json = image.with_suffix(
        ".verified.json"
    )

    extract = run_command(
        [
            "python3",
            str(
                VISION_DIR
                / "vision_extract.py"
            ),
            str(image)
        ],
        cwd=VISION_DIR,
        timeout=1800,
        label=(
            f"visual extraction "
            f"for {image.name}"
        )
    )

    if not visual_json.exists():
        raise RuntimeError(
            "Visual extraction completed "
            "but JSON file is missing: "
            f"{visual_json}"
        )

    verify = run_command(
        [
            "python3",
            str(
                VISION_DIR
                / "vision_verify.py"
            ),
            str(image),
            str(visual_json)
        ],
        cwd=VISION_DIR,
        timeout=1800,
        label=(
            f"visual verification "
            f"for {image.name}"
        )
    )

    if not verified_json.exists():
        raise RuntimeError(
            "Visual verification completed "
            "but verified JSON is missing: "
            f"{verified_json}"
        )

    return {
        "visual_json": visual_json,
        "verified_json": verified_json,
        "extract": extract,
        "verify": verify
    }


# ---------------------------------------------------------
# SANDBOX FILE TRANSFER
# ---------------------------------------------------------

def upload_verified_json(
    verified_json: Path,
    package_token: str,
    sequence: int
):
    unique_name = (
        f"{package_token}_"
        f"slide_{sequence:03d}"
        ".verified.json"
    )

    unique_local = (
        verified_json.parent
        / unique_name
    )

    shutil.copy2(
        verified_json,
        unique_local
    )

    sandbox_path = (
        f"{SANDBOX_PROCESSED}/"
        f"{unique_name}"
    )

    with unique_local.open("rb") as source:
        process = subprocess.run(
            [
                "ssh",
                SANDBOX_HOST,
                f"cat > {shlex.quote(sandbox_path)}"
            ],
            stdin=source,
            capture_output=True,
            timeout=300
        )

    if process.returncode != 0:
        raise RuntimeError(
            "Verified JSON SSH upload failed\n\n"
            + process.stderr.decode(
                errors="replace"
            )
        )

    # Verify that the file actually exists remotely.
    run_ssh(
        (
            "test -s "
            + shlex.quote(sandbox_path)
        ),
        timeout=60,
        label="verify uploaded JSON"
    )

    return {
        "local": unique_local,
        "sandbox": sandbox_path
    }


# ---------------------------------------------------------
# PACKAGE PIPELINE
# ---------------------------------------------------------

def run_package_pipeline(
    title: str,
    note: str,
    sandbox_verified_files
):
    slide_args = " ".join(
        shlex.quote(path)
        for path in sandbox_verified_files
    )

    command = (
        f"cd {SANDBOX_PROJECT} && "
        f"python3 pipeline.py "
        f"--title {shlex.quote(title)} "
        f"--slides {slide_args} "
        f"--note {shlex.quote(note)}"
    )

    result = run_ssh(
        command,
        timeout=3600,
        label="knowledge package pipeline"
    )

    matches = re.findall(
        r"PACKAGE ID:\s*(\d+)",
        result["stdout"]
    )

    if not matches:
        raise RuntimeError(
            "Sandbox pipeline completed "
            "but PACKAGE ID could not "
            "be extracted.\n\n"
            f"STDOUT:\n{result['stdout']}"
        )

    package_id = int(
        matches[-1]
    )

    result["package_id"] = package_id

    return result


# ---------------------------------------------------------
# FTS INDEX
# ---------------------------------------------------------

def rebuild_search_index():
    return run_ssh(
        (
            f"cd {SANDBOX_PROJECT} && "
            "python3 app/search_index.py"
        ),
        timeout=600,
        label="FTS5 search indexing"
    )


# ---------------------------------------------------------
# EMBEDDING
# ---------------------------------------------------------

def export_embedding_jobs():
    return run_ssh(
        (
            f"cd {SANDBOX_PROJECT} && "
            "python3 "
            "app/export_embedding_jobs.py"
        ),
        timeout=600,
        label="embedding job export"
    )


def generate_embedding(
    package_id: int,
    package_token: str
):
    work_dir = (
        RESEARCH_DIR
        / "embedding_work"
        / package_token
    )

    work_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    remote_job = (
        f"{SANDBOX_EMBEDDING_DIR}/"
        f"package_{package_id}"
        ".embedding_job.json"
    )

    run_command(
        [
            "openshell",
            "sandbox",
            "download",
            SANDBOX_NAME,
            remote_job,
            str(work_dir)
        ],
        timeout=300,
        label="download embedding job"
    )

    input_json = (
        work_dir
        / f"package_{package_id}"
        ".embedding_job.json"
    )

    if not input_json.exists():
        candidates = list(
            work_dir.glob(
                "*embedding_job.json"
            )
        )

        if len(candidates) == 1:
            input_json = candidates[0]
        else:
            raise RuntimeError(
                "Embedding job download "
                "completed but expected "
                "file was not found in "
                f"{work_dir}"
            )

    output_json = (
        work_dir
        / f"package_{package_id}"
        ".embedding_result.json"
    )

    embedding = run_command(
        [
            "python3",
            str(EMBEDDING_HOST),
            str(input_json),
            str(output_json)
        ],
        cwd=VISION_DIR,
        timeout=1800,
        label="Ollama embedding generation"
    )

    if not output_json.exists():
        raise RuntimeError(
            "embedding_host.py completed "
            "but output file does not exist: "
            f"{output_json}"
        )

    run_command(
        [
            "openshell",
            "sandbox",
            "upload",
            SANDBOX_NAME,
            str(output_json),
            SANDBOX_EMBEDDING_DIR
        ],
        timeout=300,
        label="upload embedding result"
    )

    imported = run_ssh(
        (
            f"cd {SANDBOX_PROJECT} && "
            "python3 "
            "app/import_embeddings.py"
        ),
        timeout=600,
        label="embedding import"
    )

    return {
        "input": str(input_json),
        "output": str(output_json),
        "embedding": embedding,
        "import": imported
    }


# ---------------------------------------------------------
# SQLITE SAFE SNAPSHOT
# ---------------------------------------------------------

def synchronize_database(
    package_token: str
):
    python_code = (
        "import sqlite3; "
        f"src=sqlite3.connect('{SANDBOX_DB}'); "
        f"dst=sqlite3.connect('{SANDBOX_SNAPSHOT}'); "
        "src.backup(dst); "
        "dst.close(); "
        "src.close(); "
        f"print('{SANDBOX_SNAPSHOT}')"
    )

    run_ssh(
        (
            "python3 -c "
            + shlex.quote(python_code)
        ),
        timeout=600,
        label="SQLite snapshot"
    )

    sync_dir = (
        RESEARCH_DIR
        / "db_sync"
        / package_token
    )

    sync_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    run_command(
        [
            "openshell",
            "sandbox",
            "download",
            SANDBOX_NAME,
            SANDBOX_SNAPSHOT,
            str(sync_dir)
        ],
        timeout=300,
        label="download SQLite snapshot"
    )

    snapshot = (
        sync_dir
        / "knowledge.snapshot.db"
    )

    if not snapshot.exists():
        candidates = list(
            sync_dir.glob("*.db")
        )

        if len(candidates) == 1:
            snapshot = candidates[0]
        else:
            raise RuntimeError(
                "SQLite snapshot was "
                "downloaded but could "
                "not be located"
            )

    temporary_db = (
        HOST_DB.parent
        / (
            ".knowledge.db."
            f"{package_token}.tmp"
        )
    )

    shutil.copy2(
        snapshot,
        temporary_db
    )

    os.replace(
        temporary_db,
        HOST_DB
    )

    return str(HOST_DB)


# ---------------------------------------------------------
# COMPLETE V06 UPLOAD
# ---------------------------------------------------------

@app.post("/upload")
async def upload_knowledge_v06(
    title: str = Form(...),
    note: str = Form(""),
    files: List[UploadFile] = File(...)
):
    started = time.time()

    title = title.strip()
    note = note.strip()

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

    package_token = (
        uuid.uuid4().hex[:12]
    )

    package_dir = (
        UPLOAD_ROOT
        / package_token
    )

    package_dir.mkdir(
        parents=True,
        exist_ok=False
    )

    stages = {
        "saved": False,
        "vision": False,
        "sandbox": False,
        "fts": False,
        "embedding": False,
        "database_sync": False
    }

    saved_files = []
    verified_files = []
    sandbox_files = []
    vision_diagnostics = []

    try:
        # -------------------------------------------------
        # 1. SAVE INPUT IMAGES
        # -------------------------------------------------

        for index, upload in enumerate(
            files,
            start=1
        ):
            original_name = Path(
                upload.filename
                or f"slide_{index}.jpg"
            ).name

            suffix = (
                Path(original_name)
                .suffix
                .lower()
                or ".jpg"
            )

            destination = (
                package_dir
                / f"slide_{index:03d}{suffix}"
            )

            with destination.open(
                "wb"
            ) as output:
                shutil.copyfileobj(
                    upload.file,
                    output
                )

            saved_files.append(
                destination
            )

        stages["saved"] = True

        # -------------------------------------------------
        # 2. QWEN EXTRACTION + VERIFICATION
        # -------------------------------------------------

        for index, image in enumerate(
            saved_files,
            start=1
        ):
            visual = run_visual_pipeline(
                image
            )

            verified_files.append(
                visual["verified_json"]
            )

            vision_diagnostics.append({
                "image": image.name,
                "visual_json": (
                    visual[
                        "visual_json"
                    ].name
                ),
                "verified_json": (
                    visual[
                        "verified_json"
                    ].name
                ),
                "extract_seconds": (
                    visual[
                        "extract"
                    ]["seconds"]
                ),
                "verify_seconds": (
                    visual[
                        "verify"
                    ]["seconds"]
                )
            })

            uploaded = (
                upload_verified_json(
                    visual[
                        "verified_json"
                    ],
                    package_token,
                    index
                )
            )

            sandbox_files.append(
                uploaded["sandbox"]
            )

        stages["vision"] = True

        # -------------------------------------------------
        # 3. NEMOTRON + CANONICALIZATION
        # -------------------------------------------------

        package_result = (
            run_package_pipeline(
                title,
                note,
                sandbox_files
            )
        )

        package_id = (
            package_result[
                "package_id"
            ]
        )

        stages["sandbox"] = True

        # -------------------------------------------------
        # 4. FTS5
        # -------------------------------------------------

        fts_result = (
            rebuild_search_index()
        )

        stages["fts"] = True

        # -------------------------------------------------
        # 5. EMBEDDING
        # -------------------------------------------------

        export_result = (
            export_embedding_jobs()
        )

        embedding_result = (
            generate_embedding(
                package_id,
                package_token
            )
        )

        stages["embedding"] = True

        # -------------------------------------------------
        # 6. SAFE DB SNAPSHOT -> HOST
        # -------------------------------------------------

        host_db = (
            synchronize_database(
                package_token
            )
        )

        stages[
            "database_sync"
        ] = True

        elapsed = round(
            time.time() - started,
            2
        )

        return {
            "ok": True,
            "stage": "searchable",
            "package_token": (
                package_token
            ),
            "package_id": package_id,
            "title": title,
            "note": note,
            "slides": len(
                saved_files
            ),
            "stages": stages,
            "elapsed_seconds": elapsed,
            "host_database": host_db,
            "files": [
                path.name
                for path in saved_files
            ],
            "vision": (
                vision_diagnostics
            ),
            "sandbox_verified": (
                sandbox_files
            ),
            "pipeline_seconds": (
                package_result[
                    "seconds"
                ]
            ),
            "fts_seconds": (
                fts_result[
                    "seconds"
                ]
            ),
            "embedding_seconds": (
                embedding_result[
                    "embedding"
                ]["seconds"]
            ),
            "message": (
                "Package ingested, "
                "canonicalized, indexed "
                "and synchronized. "
                "It is ready for "
                "Search and Ask."
            )
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail={
                "message": (
                    "Pipeline timed out"
                ),
                "package_token": (
                    package_token
                ),
                "stages": stages
            }
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": (
                    "v06 ingestion "
                    "pipeline failed"
                ),
                "package_token": (
                    package_token
                ),
                "stages": stages,
                "error": str(exc)
            }
        )


@app.get("/v06/status")
def v06_status():
    return {
        "ok": True,
        "version": "0.6.0",
        "pipeline": (
            "multimodal-end-to-end"
        ),
        "upload_stage": "searchable",
        "old_finalize_latest": False
    }
