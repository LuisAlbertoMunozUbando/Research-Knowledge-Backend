import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path.home() / "knowledge-agent" / "data" / "knowledge.db"
DIAG_DIR = Path.home() / "knowledge-agent" / "data" / "diagnostics"
DIAG_DIR.mkdir(parents=True, exist_ok=True)
MAX_ATTEMPTS = 3


def get_package_with_slides(package_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    package = conn.execute(
        "SELECT * FROM packages WHERE id = ?",
        (package_id,)
    ).fetchone()

    if not package:
        conn.close()
        raise ValueError(f"Package {package_id} not found")

    slides = conn.execute(
        """
        SELECT id, sequence, visual_verified
        FROM slides
        WHERE package_id = ?
        ORDER BY sequence
        """,
        (package_id,)
    ).fetchall()

    conn.close()
    return dict(package), [dict(s) for s in slides]


def clean_model_text(text: str):
    text = (text or "").strip()
    text = text.replace("\\:", ":")
    text = text.replace("```json", "")
    text = text.replace("```JSON", "")
    text = text.replace("```", "")
    return text.strip()


def _only_urls(values):
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        if not isinstance(value, str):
            continue
        value = value.strip()
        if value.startswith("http://") or value.startswith("https://"):
            result.append(value)
    return result


def sanitize_synthesis(data):
    if not isinstance(data, dict):
        raise ValueError("Synthesis result must be an object")
    data["links_visible"] = _only_urls(data.get("links_visible", []))
    data["links_mentioned"] = _only_urls(data.get("links_mentioned", []))
    return data


def extract_json(text: str):
    text = clean_model_text(text)
    if not text:
        raise ValueError("Model response is empty")

    try:
        return sanitize_synthesis(json.loads(text))
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No complete JSON object found in model response")

    candidate = clean_model_text(text[start:end + 1])
    return sanitize_synthesis(json.loads(candidate))


def _clean_list(values, limit):
    if not isinstance(values, list):
        return []
    result = []
    seen = set()
    for value in values:
        if isinstance(value, str):
            value = value.strip()
            key = value.casefold()
        elif isinstance(value, dict):
            key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            continue
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(value)
        if len(result) >= limit:
            break
    return result


def build_slide_payload(slides):
    result = []
    for slide in slides:
        verified = json.loads(slide["visual_verified"] or "{}")
        compact = {
            "sequence": slide["sequence"],
            "title": verified.get("title", ""),
            "source_type": verified.get("source_type", ""),
            "summary": str(verified.get("summary", ""))[:700],
            "topics": _clean_list(verified.get("detected_topics", []), 8),
            "people": _clean_list(verified.get("people", []), 6),
            "organizations": _clean_list(verified.get("organizations", []), 8),
            "projects": _clean_list(verified.get("projects", []), 6),
            "concepts": _clean_list(verified.get("concepts", []), 6),
            "metrics": _clean_list(verified.get("metrics", []), 4),
            "links_visible": _clean_list(verified.get("links_visible", []), 4),
            "links_mentioned": _clean_list(verified.get("links_mentioned", []), 4),
            "uncertainties": _clean_list(verified.get("uncertain_fields", []), 4),
        }
        result.append(compact)
    return result


def save_diagnostic(package_id, attempt, prompt, result=None, error=None):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = DIAG_DIR / f"synthesis_package_{package_id}_attempt_{attempt}_{stamp}.json"
    payload = {
        "package_id": package_id,
        "attempt": attempt,
        "prompt": prompt,
        "error": str(error) if error else None,
    }
    if result is not None:
        payload.update({
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        })
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def synthesize(package, slides):
    package_id = package["id"]
    slide_payload = build_slide_payload(slides)

    prompt = f"""
Eres el sintetizador de paquetes de un sistema personal de conocimiento.

Recibes VARIOS slides que pertenecen al mismo paquete temático.

OBJETIVO:
Crear una interpretación global del paquete completo, no un resumen independiente de cada slide.

REGLAS:
- Usa solamente información respaldada por los slides.
- No inventes hechos.
- No inventes URLs.
- No inventes personas u organizaciones.
- Combina información repetida.
- Elimina duplicados semánticos.
- Distingue personas, organizaciones, proyectos, productos y conceptos.
- Si dos slides parecen contradecirse, conserva la incertidumbre.
- El título debe ser corto: idealmente entre 1 y 5 palabras.
- Conserva nombres técnicos importantes.
- links_visible debe contener sólo URLs realmente visibles.
- links_mentioned debe conservar referencias a enlaces no visibles.
- Devuelve SOLAMENTE JSON válido.
- No markdown.
- No explicaciones fuera del JSON.

TÍTULO ACTUAL DEL PAQUETE:
{package["title"]}

NOTA DEL USUARIO:
{package.get("user_note", "")}

SLIDES VERIFICADOS:
{json.dumps(slide_payload, ensure_ascii=False, indent=2)}

Devuelve exactamente:
{{
  "suggested_title": "",
  "package_summary": "",
  "detected_topics": [],
  "people": [],
  "organizations": [],
  "projects": [],
  "concepts": [],
  "metrics": [],
  "links_visible": [],
  "links_mentioned": [],
  "key_points": [],
  "relationships": [],
  "uncertainties": []
}}
""".strip()

    last_error = None
    last_diag = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = subprocess.run(
            ["openclaw", "agent", "--agent", "main", "-m", prompt],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            last_error = RuntimeError("OpenClaw returned non-zero exit code")
            last_diag = save_diagnostic(package_id, attempt, prompt, result=result, error=last_error)
            continue

        try:
            return extract_json(result.stdout)
        except Exception as exc:
            last_error = exc
            last_diag = save_diagnostic(package_id, attempt, prompt, result=result, error=exc)

    raise ValueError(f"{last_error}. Diagnostic saved to {last_diag}")


def save_synthesis(package_id: int, synthesis: dict):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE packages SET package_summary = ? WHERE id = ?",
        (json.dumps(synthesis, ensure_ascii=False), package_id),
    )
    conn.commit()
    conn.close()


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 app/synthesize_package.py PACKAGE_ID")
        raise SystemExit(1)

    package_id = int(sys.argv[1])
    package, slides = get_package_with_slides(package_id)

    if not slides:
        raise ValueError(f"Package {package_id} has no slides")

    print(f"Synthesizing package {package_id} with {len(slides)} slides...")
    synthesis = synthesize(package, slides)
    save_synthesis(package_id, synthesis)
    print()
    print(json.dumps(synthesis, indent=2, ensure_ascii=False))
    print()


if __name__ == "__main__":
    main()
