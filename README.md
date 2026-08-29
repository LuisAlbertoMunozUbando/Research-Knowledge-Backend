# 🧠 Research Knowledge Hub — Backend

<p align="center">
  <strong>From scattered research evidence to searchable institutional memory.</strong>
</p>

<p align="center">
  <a href="https://knowledge.albertomunoz.ai"><img src="https://img.shields.io/badge/Live-knowledge.albertomunoz.ai-111111?style=for-the-badge&logo=vercel" alt="Live"></a>
  <img src="https://img.shields.io/badge/v1-FROZEN-2563EB?style=for-the-badge" alt="v1 Frozen">
  <img src="https://img.shields.io/badge/Input-Images%20%2B%20PDF-8B5CF6?style=for-the-badge" alt="Images and PDF">
  <img src="https://img.shields.io/badge/NVIDIA-DGX%20Spark-76B900?style=for-the-badge&logo=nvidia" alt="NVIDIA DGX Spark">
  <img src="https://img.shields.io/badge/License-MIT-F59E0B?style=for-the-badge" alt="MIT License">
</p>

---

## ✨ What is this?

**Research Knowledge Hub** is an open-source research-memory system that captures evidence, interprets it with local AI, preserves the original source, and turns the result into searchable structured knowledge.

The first stable release is deliberately **frozen at two input modalities**:

- 🖼️ **Images** — screenshots, slides, diagrams, conference photos and visual research evidence.
- 📄 **PDF papers** — born-digital research documents processed through native text extraction and a specialized PDF research agent.

Both modalities converge into the **same downstream knowledge pipeline**.

> **Preserve the evidence. Structure the knowledge. Make it searchable.**

---

## 🚦 v1 status

| Capability | Status |
|---|---|
| Image ingestion | ✅ Stable |
| PDF ingestion | ✅ Stable |
| Persistent pipeline state | ✅ |
| Resume after failure | ✅ |
| Specialized PDF agent | ✅ |
| Agent retry | ✅ |
| Deterministic PDF fallback | ✅ |
| Google Drive evidence archive | ✅ |
| SQLite / FTS5 | ✅ |
| Semantic embeddings | ✅ |
| Hybrid search | ✅ |
| Grounded RAG | ✅ |
| Vercel frontend | ✅ |
| Cloudflare Tunnel backend | ✅ |
| Audio / YouTube / Web / GitHub ingestion | ⏸️ Deferred to future versions |

**v1 is intentionally frozen here.** The goal is to keep this milestone small, reproducible and testable before expanding to additional modalities.

---

## 🏗️ Architecture

```text
                         ┌──────────────────────────┐
                         │     Researcher / Team    │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │   Next.js UI on Vercel   │
                         │ knowledge.albertomunoz.ai│
                         └────────────┬─────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │       FastAPI /upload    │
                         └────────────┬─────────────┘
                                      │
                              Resource Router
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
                    ▼                                   ▼
              🖼️ IMAGE                              📄 PDF
                    │                                   │
               Qwen2.5-VL                        PDF Inspector
                    │                                   │
          visual extraction                      native text
                    │                                   │
              verification                       PDF evidence
                    │                                   │
                    │                            pdf-researcher
                    │                                   │
                    └─────────────────┬─────────────────┘
                                      │
                                      ▼
                           Normalized Evidence
                                      │
                                      ▼
                           knowledge-synthesizer
                                      │
                                      ▼
                              Canonical JSON
                                      │
                  ┌───────────────────┼───────────────────┐
                  │                   │                   │
                  ▼                   ▼                   ▼
            ☁️ Google Drive       🔤 SQLite FTS5      🧬 Embeddings
                  │                   │                   │
                  └───────────────────┴─────────┬─────────┘
                                                ▼
                                      🔎 Search + Grounded RAG
```

The reference deployment runs its AI workloads on an **NVIDIA DGX Spark** with local inference and sandboxed agents.

---

## 🧩 Core design principle

The system deliberately separates generative interpretation from deterministic infrastructure:

> **Agents interpret evidence; deterministic software enforces contracts.**

Agents are used where semantic understanding matters. Python code remains responsible for:

- routing,
- file transfer,
- state transitions,
- schema adaptation,
- URL filtering,
- persistence,
- retries,
- deterministic fallback,
- archival,
- indexing,
- retrieval.

This keeps a generative model from becoming a single point of failure.

---

## 🖼️ Image pipeline

Supported image types in the stable release include:

- `JPG`
- `JPEG`
- `PNG`
- `WEBP`

Typical inputs include screenshots, slides, figures, diagrams and conference material.

```text
Image
  ↓
Qwen2.5-VL
  ↓
Visual extraction
  ↓
Verification
  ↓
Verified evidence
  ↓
Knowledge synthesis
```

---

## 📄 PDF pipeline

The PDF path is designed around born-digital research papers.

```text
PDF
  ↓
PDF Inspector
  ↓
Native text extraction
  ↓
Compact evidence builder
  ↓
pdf-researcher
  ↓
Schema validation
  ↓
Retry if needed
  ↓
Deterministic fallback if needed
  ↓
Verified evidence
```

The fallback path is intentional: malformed or missing agent output must not permanently block ingestion. If the specialized PDF agent fails repeatedly, deterministic evidence is preserved and passed downstream so the package can continue.

---

## 🔁 Persistent & resumable ingestion

Every upload receives a persistent package token and state file.

The stable state machine is:

```text
saved
  ↓
vision_verified
  ↓
package_created
  ↓
synthesized
  ↓
canonicalized
  ↓
drive_archived
  ↓
fts_indexed
  ↓
embedded
  ↓
database_synced
  ↓
searchable
```

`vision_verified` is retained for backward compatibility even though it now represents verified PDF evidence as well.

If a stage fails, the original upload is not lost. The package can continue through:

```text
POST /resume/{package_token}
```

The resume path has been validated after failures in the PDF generative extraction stage.

---

## 🧠 Specialized agents

The current architecture intentionally avoids a single giant universal agent.

### `pdf-researcher`
Extracts compact structured research evidence from PDF-derived text.

### `knowledge-synthesizer`
Combines verified evidence into a canonical package representation.

### Vision path
Uses Qwen2.5-VL for multimodal visual extraction and verification.

The result is a set of small cognitive components connected by deterministic software.

---

## ☁️ Evidence archive

Original uploaded resources are preserved in **Google Drive** together with structured metadata.

Reference folder:

```text
KnowledgBase
```

Archive names include the package token and sequence identifier to prevent collisions.

Example:

```text
2026-08-28__Telerobotics__...__TOKEN__slide_001.pdf
2026-08-28__Telerobotics__TOKEN__slide_001.metadata.json
```

The philosophy is explicit:

```text
original evidence
      ↓
interpretation
      ↓
structured knowledge
      ↓
retrieval
```

The original source remains available even if models, prompts or embeddings change later.

---

## 🔎 Retrieval layer

Research Knowledge Hub combines:

- 🔤 **SQLite FTS5** for lexical retrieval
- 🧬 **semantic embeddings** using `nomic-embed-text`
- ⚖️ **hybrid ranking** across lexical and semantic signals
- 💬 **grounded RAG** over retrieved packages

Google Drive is the evidence archive. Search is performed from the structured database and local indexes rather than by searching Drive directly.

---

## ⚙️ Technology stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Hosting | Vercel |
| Public backend | FastAPI + Uvicorn |
| Secure exposure | Cloudflare Tunnel |
| GPU host | NVIDIA DGX Spark |
| Vision | Qwen2.5-VL |
| Agent model | Nemotron |
| Local inference | Ollama |
| Agent runtime | OpenClaw / NemoClaw / OpenShell |
| Lexical retrieval | SQLite FTS5 |
| Semantic retrieval | `nomic-embed-text` |
| Evidence archive | Google Drive + `rclone` |

---

## 🌐 Production topology

```text
https://knowledge.albertomunoz.ai
              │
              ▼
           Vercel
              │
              ▼
https://knowledge-api.albertomunoz.ai
              │
              ▼
      Cloudflare Tunnel
              │
              ▼
   FastAPI on DGX Spark :8010
```

The backend route resolves through the `slideextractor-spark` Cloudflare Tunnel while local inference services remain private.

---

## 🚀 API health check

```bash
curl https://knowledge-api.albertomunoz.ai/v08/status
```

Expected shape:

```json
{
  "ok": true,
  "version": "0.8.1",
  "pipeline": "persistent-resumable"
}
```

---

## 🗂️ Repository structure

Representative host-side structure:

```text
research-knowledge/
├── api_v08.py
├── pipeline_state.py
├── drive_archive.py
├── process_pdf_resource.py
├── pdf_inspector.py
├── build_pdf_evidence.py
├── rag.py
├── uploads/               # runtime / ignored
├── pipeline_states/       # runtime / ignored
├── embedding_work/        # runtime / ignored
├── db_sync/               # runtime / ignored
└── data/
    └── knowledge.db       # runtime / ignored
```

---

## 🔐 Security boundaries

Never commit or expose:

```text
rclone.conf
OAuth credentials
client secrets
access tokens
refresh tokens
.env files containing secrets
OpenClaw provider credentials
runtime databases
pipeline states
uploaded evidence
```

Only the intended FastAPI endpoint should be exposed publicly. Ollama, OpenClaw, OpenShell and model endpoints should remain private.

---

## 🖥️ Frontend repository

Frontend source:

**[LuisAlbertoMunozUbando/Research-Knowledge-Hub](https://github.com/LuisAlbertoMunozUbando/Research-Knowledge-Hub)**

Production site:

**[https://knowledge.albertomunoz.ai](https://knowledge.albertomunoz.ai)**

The frontend should use:

```env
KNOWLEDGE_API_URL=https://knowledge-api.albertomunoz.ai
```

---

## 🧭 v1 scope freeze

This release intentionally stops at:

```text
Images ✅
PDFs   ✅
```

Future adapters such as audio, YouTube, web URLs, GitHub repositories, WhatsApp and email are intentionally **out of scope for v1**.

That decision is part of the architecture, not a missing feature: the objective is to keep the first release understandable, reproducible and robust.

---

## 🧪 Research philosophy

1. **Preserve original evidence.** AI interpretations can change.
2. **Make generated knowledge regenerable.** Summaries and embeddings are computational products.
3. **Keep provenance explicit.** Evidence should remain connected to interpretation.
4. **Use agents for semantics, not infrastructure.** Deterministic code should own critical state and contracts.
5. **Prefer resilience over elegance.** A malformed model response should not destroy an ingestion job.
6. **Keep research memory under the control of the research team.**

---

## ❤️ Why build this?

Research groups constantly accumulate useful fragments:

```text
screenshots
papers
slides
diagrams
conference material
research notes
people
projects
companies
methods
results
ideas
```

Most of those fragments disappear into personal folders, browser tabs, chats and phones.

Research Knowledge Hub is an attempt to turn those fragments into a **shared, searchable memory with provenance**.

> **Capture knowledge. Preserve evidence. Connect research.**

---

## 📄 License

Released under the **MIT License**.

---

<p align="center">
  🧠 + 🔬 + 🤖 + 📚 = searchable research memory
</p>
