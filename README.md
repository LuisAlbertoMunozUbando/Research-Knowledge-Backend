# Research Knowledge Hub — Backend

Open-source backend for a collaborative multimodal research-memory system running on local GPU infrastructure.

The current stable scope deliberately supports **images and PDF papers**. Both modalities are converted into structured evidence and then converge into the same synthesis, archival, retrieval and search pipeline.

## Current production architecture

```text
                       Research Knowledge Hub
                                |
                                v
                        FastAPI /upload
                                |
                         resource router
                                |
                  +-------------+-------------+
                  |                           |
                  v                           v
              IMAGE                         PDF
                  |                           |
            Qwen2.5-VL                 PDF Inspector
                  |                           |
           visual extraction             native text
                  |                           |
             verification              PDF evidence
                  |                           |
                  |                    pdf-researcher
                  |                           |
                  +-------------+-------------+
                                |
                                v
                       normalized evidence
                                |
                                v
                     knowledge-synthesizer
                                |
                                v
                        canonical JSON
                                |
                    +-----------+-----------+
                    |           |           |
                    v           v           v
               Google Drive    FTS5     embeddings
                                |
                                v
                            searchable
```

The reference implementation runs its AI workloads on an **NVIDIA DGX Spark** using local inference and a sandboxed agent layer.

## Supported resource types

### Images

- JPG / JPEG
- PNG
- WEBP
- screenshots
- slides
- conference photos and visual research evidence

The image path uses a vision-language model for extraction followed by verification before knowledge synthesis.

### PDF

The PDF path currently targets born-digital research papers. The pipeline performs deterministic PDF inspection and native text extraction, builds compact evidence, invokes a specialized `pdf-researcher`, normalizes the result and sends it to the same downstream knowledge synthesizer used by images.

The first PDF end-to-end test reached the complete persistent state machine successfully:

```text
saved
  -> vision_verified
  -> package_created
  -> synthesized
  -> canonicalized
  -> drive_archived
  -> fts_indexed
  -> embedded
  -> database_synced
  -> searchable
```

`vision_verified` is retained as the current state name for backward compatibility even though it now also represents verified PDF evidence. A future schema migration may rename it to `evidence_verified`.

## Resumable ingestion

Every upload has a persistent package token and state file. If a processing stage fails, the resource does not need to be uploaded again.

The `/resume/{package_token}` path can reconstruct missing verified evidence from the saved resource and continue processing. This has been validated with the PDF pipeline after failures in the generative extraction stage.

## Specialized agents

The system avoids one large universal agent. Specialized components perform compact, well-defined tasks:

- image extraction / verification
- `pdf-researcher`
- `knowledge-synthesizer`

Deterministic Python code is responsible for routing, file movement, schema adaptation, URL filtering, state transitions, persistence and retrieval operations.

A key design principle is:

> Agents interpret evidence; deterministic software enforces contracts.

The PDF researcher uses compact prompts and an automatic retry path when the first generative response is not valid JSON. Raw agent responses are preserved for diagnosis rather than silently repairing malformed semantic output.

## Evidence archive

Original source resources are preserved in Google Drive together with generated metadata. The reference folder is:

```text
KnowledgBase
```

Archive filenames include the package token and sequence identifier so that multi-resource packages do not overwrite one another.

Example:

```text
2026-08-28__Visual-Pose-Tracking-Teleoperation__...__TOKEN__slide_001.pdf
2026-08-28__Visual-Pose-Tracking-Teleoperation__TOKEN__slide_001.metadata.json
```

## Retrieval

The searchable layer combines:

- SQLite
- FTS5 lexical retrieval
- semantic embeddings
- `nomic-embed-text`
- hybrid lexical + semantic ranking
- grounded RAG answers

Google Drive is the evidence archive; retrieval is performed from the structured local database and indexes rather than by searching Drive directly.

## Infrastructure

```text
Next.js / Vercel
       |
       v
knowledge.albertomunoz.ai
       |
       v
knowledge-api.albertomunoz.ai
       |
       v
Cloudflare Tunnel
       |
       v
FastAPI on NVIDIA DGX Spark
       |
       +-- OpenShell sandbox
       +-- OpenClaw / NemoClaw
       +-- Ollama
       +-- Qwen2.5-VL
       +-- Nemotron
       +-- SQLite / FTS5
       +-- embeddings
       +-- Google Drive archive
```

Only the FastAPI service is intended to be exposed through the HTTPS tunnel. Ollama, OpenClaw, OpenShell and inference services should remain private.

## Important security rule

Never commit any of the following:

```text
rclone.conf
OAuth credentials
client secrets
access tokens
refresh tokens
.env files containing secrets
OpenClaw provider credentials
```

The repository `.gitignore` should continue to exclude runtime databases, upload folders, pipeline states, temporary embedding work, backups and secrets.

## Frontend

The frontend lives at:

https://github.com/LuisAlbertoMunozUbando/Research-Knowledge-Hub

Its production backend variable is intended to be:

```env
KNOWLEDGE_API_URL=https://knowledge-api.albertomunoz.ai
```

The intended public frontend hostname is:

```text
knowledge.albertomunoz.ai
```

## Current scope decision

For the current milestone the project is intentionally stopping at **images + PDFs**. Audio, YouTube, web URLs, GitHub repositories and other ingestion adapters remain natural future extensions, but they are not part of this stable milestone.

This keeps the architecture testable and gives the image and PDF pipelines time to mature before broadening modality support.

## Philosophy

Preserve evidence first. Make AI-generated knowledge regenerable. Keep provenance explicit. Separate interpretation from deterministic validation. Keep local research memory under the control of the research team.

## License

MIT.
