import json
from pathlib import Path
from datetime import datetime, timezone

STATE_DIR = Path.home() / "research-knowledge" / "pipeline_states"
STATE_DIR.mkdir(parents=True, exist_ok=True)

STAGES = [
    "saved",
    "vision_verified",
    "package_created",
    "synthesized",
    "canonicalized",
    "fts_indexed",
    "embedded",
    "database_synced",
    "searchable",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def state_path(package_token):
    return STATE_DIR / f"{package_token}.json"


def save_state(data):
    data["updated_at"] = now()

    tmp = state_path(data["package_token"]).with_suffix(".tmp")

    tmp.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    tmp.replace(
        state_path(data["package_token"])
    )


def new_state(
    package_token,
    title,
    note,
    files
):
    data = {
        "package_token": package_token,
        "title": title,
        "note": note,
        "files": files,
        "saved_files": [],
        "sandbox_files": [],
        "package_id": None,
        "current_stage": None,
        "completed_stages": [],
        "failed_stage": None,
        "error": None,
        "created_at": now(),
        "updated_at": now(),
    }

    save_state(data)
    return data


def load_state(package_token):
    path = state_path(package_token)

    if not path.exists():
        raise FileNotFoundError(
            package_token
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def mark_complete(
    data,
    stage,
    **extra
):
    if stage not in STAGES:
        raise ValueError(
            f"Unknown stage: {stage}"
        )

    if stage not in data["completed_stages"]:
        data["completed_stages"].append(
            stage
        )

    data["current_stage"] = stage
    data["failed_stage"] = None
    data["error"] = None

    data.update(extra)

    save_state(data)
    return data


def mark_failed(
    data,
    stage,
    error
):
    data["failed_stage"] = stage
    data["error"] = str(error)

    save_state(data)
    return data


def is_complete(
    data,
    stage
):
    return stage in data.get(
        "completed_stages",
        []
    )
