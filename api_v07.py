from fastapi import HTTPException

from api_v06 import app
from pipeline_state import load_state


@app.get("/pipeline/{package_token}")
def pipeline_status(package_token: str):
    try:
        state = load_state(package_token)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Pipeline state not found",
        )

    return {
        "ok": True,
        **state,
    }
