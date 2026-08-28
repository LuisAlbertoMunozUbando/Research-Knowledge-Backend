import json
import re
import shlex
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import List

from fastapi import File, Form, HTTPException, UploadFile

from api_v07 import app
from api_v06 import (
    remove_route,
    run_visual_pipeline,
    upload_verified_json,
    rebuild_search_index,
    export_embedding_jobs,
    generate_embedding,
    synchronize_database,
    run_ssh,
    UPLOAD_ROOT,
    SANDBOX_HOST,
    SANDBOX_PROJECT,
)

from pipeline_state import (
    new_state,
    load_state,
    mark_complete,
    mark_failed,
    is_complete,
)


# ---------------------------------------------------------
# Replace previous /upload
# ---------------------------------------------------------

remove_route("/upload", "POST")


# ---------------------------------------------------------
# Sandbox package inspection
# ---------------------------------------------------------

def inspect_package(package_id):
    code = f'''
import json
import sqlite3
from pathlib import Path

db = Path.home() / "knowledge-agent" / "data" / "knowledge.db"

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

row = conn.execute(
    """
    SELECT
        id,
        status,
        package_summary,
        package_final
    FROM packages
    WHERE id = ?
    """,
    ({int(package_id)},)
).fetchone()

conn.close()

if not row:
    raise SystemExit("PACKAGE_NOT_FOUND")

print(json.dumps({{
    "id": row["id"],
    "status": row["status"],
    "has_summary": bool(row["package_summary"]),
    "has_final": bool(row["package_final"])
}}))
'''

    result = run_ssh(
        "python3 -c "
        + shlex.quote(code),
        timeout=120,
        label="inspect sandbox package"
    )

    lines = [
        line.strip()
        for line in result["stdout"].splitlines()
        if line.strip()
    ]

    if not lines:
        raise RuntimeError(
            "Package inspection returned no output"
        )

    return json.loads(lines[-1])


# ---------------------------------------------------------
# Initial sandbox pipeline
# ---------------------------------------------------------

def run_initial_package_pipeline(
    title,
    note,
    sandbox_files
):
    slide_args = " ".join(
        shlex.quote(path)
        for path in sandbox_files
    )

    command = (
        f"cd {SANDBOX_PROJECT} && "
        "python3 pipeline.py "
        f"--title {shlex.quote(title)} "
        f"--slides {slide_args} "
        f"--note {shlex.quote(note)}"
    )

    process = subprocess.run(
        [
            "ssh",
            SANDBOX_HOST,
            command
        ],
        capture_output=True,
        text=True,
        timeout=3600
    )

    matches = re.findall(
        r"(?:ID:|PACKAGE ID:)\s*(\d+)",
        process.stdout
    )

    package_id = (
        int(matches[-1])
        if matches
        else None
    )

    return {
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "package_id": package_id,
    }


# ---------------------------------------------------------
# Resume sandbox intelligence
# ---------------------------------------------------------

def finish_sandbox_package(
    state
):
    package_id = state.get(
        "package_id"
    )

    if not package_id:
        raise RuntimeError(
            "Cannot resume sandbox work "
            "without package_id"
        )

    info = inspect_package(
        package_id
    )

    if info["has_summary"]:
        if not is_complete(
            state,
            "synthesized"
        ):
            mark_complete(
                state,
                "synthesized"
            )
    else:
        run_ssh(
            (
                f"cd {SANDBOX_PROJECT} && "
                "python3 "
                "app/synthesize_package.py "
                f"{package_id}"
            ),
            timeout=3600,
            label="resume synthesis"
        )

        mark_complete(
            state,
            "synthesized"
        )

    info = inspect_package(
        package_id
    )

    if info["has_final"]:
        if not is_complete(
            state,
            "canonicalized"
        ):
            mark_complete(
                state,
                "canonicalized"
            )
    else:
        run_ssh(
            (
                f"cd {SANDBOX_PROJECT} && "
                "python3 "
                "app/canonicalize_package.py "
                f"{package_id}"
            ),
            timeout=600,
            label="resume canonicalization"
        )

        mark_complete(
            state,
            "canonicalized"
        )


# ---------------------------------------------------------
# Continue from current state
# ---------------------------------------------------------

def continue_pipeline(
    state
):
    package_token = state[
        "package_token"
    ]

    # -----------------------------------------
    # RESOURCE PROCESSING / VERIFIED EVIDENCE
    # -----------------------------------------
    #
    # A package may have been saved successfully
    # but failed before its resources were
    # transformed into verified sandbox evidence.
    #
    # This block makes resume possible from
    # the "saved" stage for both images and PDFs.

    if (
        is_complete(
            state,
            "saved"
        )
        and not is_complete(
            state,
            "vision_verified"
        )
    ):
        saved_files = state.get(
            "saved_files",
            []
        )

        if not saved_files:
            raise RuntimeError(
                "Saved stage is complete but "
                "saved_files is empty"
            )

        sandbox_files = []

        for index, filename in enumerate(
            saved_files,
            start=1
        ):
            resource = Path(filename)

            if not resource.exists():
                raise RuntimeError(
                    "Saved resource no longer exists: "
                    + str(resource)
                )

            suffix = (
                resource.suffix.lower()
            )

            if suffix == ".pdf":
                pdf_result = (
                    run_pdf_resource_pipeline(
                        resource,
                        package_token,
                        index
                    )
                )

                sandbox_files.append(
                    pdf_result[
                        "verified_json"
                    ]
                )

            elif suffix in {
                ".jpg",
                ".jpeg",
                ".png",
                ".webp"
            }:
                visual = (
                    run_visual_pipeline(
                        resource
                    )
                )

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

            else:
                raise RuntimeError(
                    "Unsupported resource type: "
                    + suffix
                )

        mark_complete(
            state,
            "vision_verified",
            sandbox_files=sandbox_files
        )

    # -----------------------------------------
    # PACKAGE CREATION / SYNTHESIS
    # -----------------------------------------

    if not is_complete(
        state,
        "package_created"
    ):
        sandbox_files = state.get(
            "sandbox_files",
            []
        )

        if not sandbox_files:
            raise RuntimeError(
                "No sandbox verified files "
                "available"
            )

        result = (
            run_initial_package_pipeline(
                state["title"],
                state.get("note", ""),
                sandbox_files
            )
        )

        if result["package_id"]:
            state["package_id"] = (
                result["package_id"]
            )

            mark_complete(
                state,
                "package_created",
                package_id=(
                    result["package_id"]
                )
            )

        if result["returncode"] != 0:
            raise RuntimeError(
                "Sandbox package pipeline "
                "stopped after package "
                "creation.\n\n"
                f"STDOUT:\n"
                f"{result['stdout']}\n\n"
                f"STDERR:\n"
                f"{result['stderr']}"
            )

        # pipeline.py succeeded completely.
        mark_complete(
            state,
            "synthesized"
        )

        mark_complete(
            state,
            "canonicalized"
        )

    # If previous run created package
    # but failed during generative stages.
    if (
        is_complete(
            state,
            "package_created"
        )
        and not is_complete(
            state,
            "canonicalized"
        )
    ):
        finish_sandbox_package(
            state
        )

    # -----------------------------------------
    # GOOGLE DRIVE ARCHIVE
    # -----------------------------------------

    if not is_complete(
        state,
        "drive_archived"
    ):
        package_id = int(state["package_id"])

        code = f"""
import json
import sqlite3
from pathlib import Path

db = Path.home() / "knowledge-agent" / "data" / "knowledge.db"

conn = sqlite3.connect(db)
row = conn.execute(
    "SELECT title, package_final FROM packages WHERE id=?",
    ({package_id},)
).fetchone()
conn.close()

if not row:
    raise SystemExit("PACKAGE_NOT_FOUND")

title, package_final = row
data = json.loads(package_final or "{{}}")

print(json.dumps({{
    "title": title,
    "summary": data.get("summary", ""),
    "topics": data.get("detected_topics", [])
}}, ensure_ascii=False))
"""

        info_result = run_ssh(
            "python3 -c " + shlex.quote(code),
            timeout=120,
            label="fetch Drive metadata"
        )

        lines = [
            line.strip()
            for line in info_result["stdout"].splitlines()
            if line.strip()
        ]

        if not lines:
            raise RuntimeError(
                "No metadata returned for Drive archive"
            )

        info = json.loads(lines[-1])

        drive_results = []

        for image_path in state.get(
            "saved_files",
            []
        ):
            process = subprocess.run(
                [
                    "python3",
                    str(
                        Path.home()
                        / "research-knowledge"
                        / "drive_archive.py"
                    ),
                    "--image",
                    image_path,
                    "--title",
                    info["title"],
                    "--token",
                    package_token,
                    "--summary",
                    info["summary"],
                    "--keywords",
                    ",".join(info["topics"])
                ],
                capture_output=True,
                text=True,
                timeout=600
            )

            if process.returncode != 0:
                raise RuntimeError(
                    "Drive archive failed\n\n"
                    f"STDOUT:\n{process.stdout}\n\n"
                    f"STDERR:\n{process.stderr}"
                )

            drive_results.append(
                json.loads(process.stdout)
            )

        mark_complete(
            state,
            "drive_archived",
            drive_files=drive_results
        )

    # -----------------------------------------
    # FTS5
    # -----------------------------------------

    if not is_complete(
        state,
        "fts_indexed"
    ):
        rebuild_search_index()

        mark_complete(
            state,
            "fts_indexed"
        )

    # -----------------------------------------
    # EMBEDDING
    # -----------------------------------------

    if not is_complete(
        state,
        "embedded"
    ):
        export_embedding_jobs()

        generate_embedding(
            int(state["package_id"]),
            package_token
        )

        mark_complete(
            state,
            "embedded"
        )

    # -----------------------------------------
    # DB SYNC
    # -----------------------------------------

    if not is_complete(
        state,
        "database_synced"
    ):
        host_db = (
            synchronize_database(
                package_token
            )
        )

        mark_complete(
            state,
            "database_synced",
            host_database=host_db
        )

    # -----------------------------------------
    # READY
    # -----------------------------------------

    if not is_complete(
        state,
        "searchable"
    ):
        mark_complete(
            state,
            "searchable"
        )

    return state



# ---------------------------------------------------------
# PDF RESOURCE PIPELINE
# ---------------------------------------------------------

def run_pdf_resource_pipeline(
    pdf_path,
    package_token,
    index
):
    pdf_path = Path(pdf_path)

    sandbox_project = "/sandbox/knowledge-agent"

    remote_raw_dir = (
        f"{sandbox_project}/data/raw"
    )

    suffix = (
        pdf_path.suffix.lower()
        or ".pdf"
    )

    remote_pdf = (
        f"{remote_raw_dir}/"
        f"{package_token}_pdf_{index:03d}"
        f"{suffix}"
    )

    # Transfer original PDF to sandbox through SSH stdin.
    # We deliberately avoid SCP/SFTP because the sandbox
    # does not expose an SFTP server.
    transfer = subprocess.run(
        [
            "ssh",
            SANDBOX_HOST,
            (
                f"mkdir -p "
                f"{shlex.quote(remote_raw_dir)} "
                f"&& cat > "
                f"{shlex.quote(remote_pdf)}"
            )
        ],
        input=pdf_path.read_bytes(),
        capture_output=True,
        timeout=600
    )

    if transfer.returncode != 0:
        stderr = transfer.stderr.decode(
            "utf-8",
            errors="replace"
        )

        raise RuntimeError(
            "PDF transfer to sandbox failed\n\n"
            + stderr
        )

    command = (
        f"cd {shlex.quote(sandbox_project)} "
        f"&& python3 "
        f"app/process_pdf_resource.py "
        f"{shlex.quote(remote_pdf)} "
        f"--token "
        f"{shlex.quote(package_token)} "
        f"--index {int(index)}"
    )

    process = subprocess.run(
        [
            "ssh",
            SANDBOX_HOST,
            command
        ],
        capture_output=True,
        text=True,
        timeout=1800
    )

    if process.returncode != 0:
        raise RuntimeError(
            "PDF resource pipeline failed\n\n"
            f"STDOUT:\n{process.stdout}\n\n"
            f"STDERR:\n{process.stderr}"
        )

    stdout = process.stdout.strip()

    if not stdout:
        raise RuntimeError(
            "PDF resource pipeline "
            "returned no output"
        )

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Could not parse PDF pipeline output\n\n"
            f"{stdout}"
        ) from exc

    verified_json = result.get(
        "verified_json"
    )

    if not verified_json:
        raise RuntimeError(
            "PDF pipeline did not return "
            "verified_json"
        )

    return result


# ---------------------------------------------------------
# NEW UPLOAD
# ---------------------------------------------------------

@app.post("/upload")
async def upload_v08(
    title: str = Form(...),
    note: str = Form(""),
    files: List[UploadFile] = File(...)
):
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
            detail="At least one file is required"
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

    state = new_state(
        package_token,
        title,
        note,
        [
            upload.filename
            for upload in files
        ]
    )

    try:
        saved_files = []

        for index, upload in enumerate(
            files,
            start=1
        ):
            original = Path(
                upload.filename
                or f"slide_{index}.jpg"
            ).name

            suffix = (
                Path(original)
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
                str(destination)
            )

        mark_complete(
            state,
            "saved",
            saved_files=saved_files
        )

        sandbox_files = []

        for index, filename in enumerate(
            saved_files,
            start=1
        ):
            resource = Path(filename)

            suffix = (
                resource.suffix.lower()
            )

            if suffix == ".pdf":
                pdf_result = (
                    run_pdf_resource_pipeline(
                        resource,
                        package_token,
                        index
                    )
                )

                sandbox_files.append(
                    pdf_result[
                        "verified_json"
                    ]
                )

            else:
                visual = (
                    run_visual_pipeline(
                        resource
                    )
                )

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

        mark_complete(
            state,
            "vision_verified",
            sandbox_files=sandbox_files
        )

        state = continue_pipeline(
            state
        )

        return {
            "ok": True,
            "stage": "searchable",
            **state
        }

    except Exception as exc:
        current = state.get(
            "current_stage"
        )

        failed_stage = (
            "pipeline_after_"
            + str(current)
        )

        mark_failed(
            state,
            failed_stage,
            exc
        )

        raise HTTPException(
            status_code=500,
            detail={
                "message": (
                    "Ingestion paused. "
                    "The package can be resumed."
                ),
                "package_token": (
                    package_token
                ),
                "package_id": (
                    state.get(
                        "package_id"
                    )
                ),
                "current_stage": (
                    state.get(
                        "current_stage"
                    )
                ),
                "failed_stage": (
                    state.get(
                        "failed_stage"
                    )
                ),
                "error": str(exc)
            }
        )


# ---------------------------------------------------------
# RESUME
# ---------------------------------------------------------

@app.post(
    "/resume/{package_token}"
)
def resume_pipeline(
    package_token: str
):
    try:
        state = load_state(
            package_token
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Pipeline state not found"
        )

    try:
        state = continue_pipeline(
            state
        )

        return {
            "ok": True,
            "resumed": True,
            "stage": "searchable",
            **state
        }

    except Exception as exc:
        mark_failed(
            state,
            (
                "pipeline_after_"
                + str(
                    state.get(
                        "current_stage"
                    )
                )
            ),
            exc
        )

        raise HTTPException(
            status_code=500,
            detail={
                "message": (
                    "Resume paused again"
                ),
                "package_token": (
                    package_token
                ),
                "package_id": (
                    state.get(
                        "package_id"
                    )
                ),
                "current_stage": (
                    state.get(
                        "current_stage"
                    )
                ),
                "error": str(exc)
            }
        )


@app.get("/v08/status")
def v08_status():
    return {
        "ok": True,
        "version": "0.8.1",
        "pipeline": "persistent-resumable",
        "resume_endpoint": (
            "/resume/{package_token}"
        ),
        "state_endpoint": (
            "/pipeline/{package_token}"
        )
    }
