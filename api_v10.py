import api_v08 as _v08

from api_v09 import app
from pdf_visual_fallback import run_pdf_with_visual_fallback


# ---------------------------------------------------------
# PDF quality-aware bridge
# ---------------------------------------------------------
#
# api_v09 already solved the HTTP timeout problem by making
# uploads asynchronous. api_v10 keeps that behavior and adds
# a quality-aware PDF bridge: normal born-digital PDFs use the
# existing native-text pipeline; PDFs with broken font/text
# encodings are automatically rendered and interpreted through
# the existing Qwen2.5-VL visual pipeline before indexing.

_BASE_PDF_PIPELINE = _v08.run_pdf_resource_pipeline


def _quality_aware_pdf_pipeline(
    pdf_path,
    package_token,
    index,
):
    return run_pdf_with_visual_fallback(
        _BASE_PDF_PIPELINE,
        pdf_path,
        package_token,
        index,
    )


# continue_pipeline() is defined in api_v08 and resolves this
# function from the api_v08 module namespace at runtime.
_v08.run_pdf_resource_pipeline = _quality_aware_pdf_pipeline


@app.get("/v10/status")
def v10_status():
    return {
        "ok": True,
        "version": "0.10.0",
        "pipeline": "persistent-resumable-async",
        "upload_behavior": "202-accepted-background-processing",
        "pdf_ingestion": "quality-aware-native-plus-visual-fallback",
        "visual_pdf_fallback": "Qwen2.5-VL",
        "state_endpoint": "/pipeline/{package_token}",
        "resume_endpoint": "/resume/{package_token}",
    }
