# 🧠 Research Knowledge Hub

### Turn your research team's images, screenshots, slides and visual evidence into a searchable collective memory.

[![Open Source](https://img.shields.io/badge/Open%20Source-Yes-brightgreen)](#-open-source)
[![DGX Spark](https://img.shields.io/badge/NVIDIA-DGX%20Spark-76B900)](#-architecture)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-Frontend-black)](https://nextjs.org/)
[![Google Drive](https://img.shields.io/badge/Google%20Drive-Knowledge%20Archive-4285F4)](#-knowledge-archive)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#-license)

---

## 🌍 Why this project?

Research teams generate enormous amounts of useful information every day:

- screenshots from papers and social networks,
- diagrams,
- slides,
- conference material,
- experimental results,
- robotics projects,
- code references,
- companies,
- researchers,
- technologies,
- URLs,
- datasets,
- ideas worth revisiting.

Most of that knowledge is eventually lost inside phones, messaging apps, browser tabs or personal folders.

**Research Knowledge Hub turns those fragments into shared research memory.**

Upload an image, let the local AI pipeline understand it, extract structured knowledge, archive the original evidence and make the resulting information searchable by your team.

> **Do not just collect information. Build institutional memory.**

---

# ✨ What it does

A researcher uploads one or more images.

The system automatically:

📥 **captures the original evidence**

👁️ **understands the image using a Vision-Language Model**

🔎 **verifies the extracted information**

🧠 **synthesizes knowledge across multiple images**

🏷️ **extracts topics, people, organizations, projects and concepts**

🧹 **canonicalizes noisy AI/OCR output**

☁️ **archives the original image in Google Drive**

🗂️ **creates structured metadata**

🔤 **indexes the information with FTS5**

🧬 **creates semantic embeddings**

🔍 **enables hybrid lexical + semantic search**

💬 **supports grounded questions over the research collection**

---

# 🚀 The idea

Instead of this:

```text
WhatsApp
Screenshots
Downloads
Bookmarks
Browser tabs
Google Drive folders
Personal notes
Conference photos
LinkedIn posts
Papers
```

we want this:

```text
                 Research Team
                      │
                      ▼
               Upload Evidence
                      │
                      ▼
              Multimodal Analysis
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
 Structured Knowledge      Original Evidence
         │                         │
         ▼                         ▼
 Search + RAG                Google Drive
         │
         ▼
 Collective Research Memory
```

---

# 🏗️ Architecture

The current implementation combines cloud accessibility with local AI infrastructure.

```text
                           ┌─────────────────────┐
                           │    Research Team    │
                           │ Phone / Laptop / Web│
                           └──────────┬──────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │       Vercel        │
                           │    Next.js UI       │
                           └──────────┬──────────┘
                                      │
                                      ▼
                     https://knowledge-api.example.org
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │     Cloudflare      │
                           │       Tunnel        │
                           └──────────┬──────────┘
                                      │
                                      ▼
                         ┌────────────────────────┐
                         │   NVIDIA DGX Spark     │
                         │                        │
                         │      FastAPI API       │
                         │          │             │
                         │          ▼             │
                         │   Qwen2.5-VL Vision    │
                         │          │             │
                         │          ▼             │
                         │ Nemotron / Agent Layer │
                         │          │             │
                         │          ▼             │
                         │   Canonicalization     │
                         │          │             │
                         │     ┌────┴────┐        │
                         │     ▼         ▼        │
                         │   SQLite   Embeddings  │
                         │    FTS5    Ollama      │
                         └─────┬─────────┬────────┘
                               │         │
                               ▼         ▼
                          Hybrid Search
                               │
                               ▼
                         Grounded Answers

                               +
                               │
                               ▼
                       ┌───────────────┐
                       │ Google Drive  │
                       │ KnowledgBase  │
                       │ Original Data │
                       └───────────────┘
```

---

# 🧩 Technology Stack

## 🖥️ Frontend
- Next.js
- React
- TypeScript
- Tailwind CSS
- Vercel

## ⚙️ Backend
- Python
- FastAPI
- Uvicorn
- systemd
- Cloudflare Tunnel

## 🧠 AI
- Qwen2.5-VL
- Nemotron
- Ollama
- local inference
- multimodal extraction
- structured synthesis
- retrieval-augmented generation

## 🔎 Retrieval
- SQLite
- FTS5
- semantic embeddings
- `nomic-embed-text`
- hybrid lexical + semantic ranking

## ☁️ Evidence Archive
- Google Drive
- `rclone`
- structured JSON metadata

## 🧪 Agent Infrastructure
- NemoClaw
- OpenClaw
- OpenShell sandboxing

---

# 🔄 Ingestion Pipeline

Every upload moves through a persistent pipeline.

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

---

# 📷 Knowledge Archive

The original image is preserved together with structured metadata.

Example:

```text
KnowledgBase/
├── 2026-08-27__China-Robotics__robotics-technology__TOKEN.png
└── 2026-08-27__China-Robotics__TOKEN.metadata.json
```

This creates an explicit relationship between:

**evidence → interpretation → retrieval**

rather than storing AI-generated summaries without provenance.

---

# 🔎 Hybrid Search

Research Knowledge Hub combines lexical search with semantic retrieval.

### Lexical Search
SQLite FTS5 finds direct textual matches.

### Semantic Search
Embeddings find conceptually related information even when terminology differs.

### Hybrid Retrieval
Both signals are combined to improve research discovery.

---

# 💬 Ask the Library

Examples:

```text
What evidence have we collected about humanoid robotics?
```

```text
Which organizations appear frequently in our embodied AI material?
```

```text
What projects in our collection use ROS 2?
```

```text
What have we collected about Chinese robotics companies?
```

The objective is not to replace researchers.

The objective is to make the team's accumulated evidence easier to recover, connect and discuss.

---

# 👩‍🔬 Built for Research Teams

The project is designed around a simple idea:

> **Knowledge becomes more valuable when a research group can accumulate it together.**

One researcher sees an interesting robotics paper.

Another discovers a startup.

A student captures a useful architecture.

Someone attends a conference.

Another person finds an important GitHub repository.

Instead of those discoveries remaining isolated, they become part of a common searchable memory.

---

# 🌱 Grow Knowledge Together

We would love to see laboratories, universities and independent research groups adapt this project.

Use it to build:

🤖 robotics knowledge bases

🧬 biomedical research collections

🧠 AI literature repositories

🏭 industrial intelligence archives

📚 teaching knowledge systems

🔬 laboratory research memory

🌎 collaborative international research collections

🏢 corporate R&D intelligence systems

The code is intended to be modified.

Change the models.

Change the database.

Change the frontend.

Change the retrieval strategy.

Add another storage backend.

Connect agents.

Build your own research memory.

---

# 🆓 Open Source

The goal of this project is to make the complete architecture reproducible and extensible.

The project source code can be released under the **MIT License**.

Third-party models, frameworks and services may have their own licenses and terms.

---

# 🔐 Privacy by Architecture

The current architecture was designed so that computationally sensitive AI components can run locally.

The DGX Spark can host:

- multimodal inference,
- embeddings,
- retrieval,
- SQLite,
- agent execution,
- pipeline orchestration.

Only the services explicitly exposed through the API need to be reachable externally.

---

# ⚡ NVIDIA DGX Spark

The reference implementation currently runs its AI workloads on an NVIDIA DGX Spark.

The architecture is not restricted to DGX Spark and can be adapted to:

- workstation GPUs,
- servers,
- university clusters,
- cloud GPUs,
- Jetson-based edge systems,
- hybrid infrastructure.

---

# 🛠️ Repository Structure

```text
research-knowledge/
├── api_v08.py
├── pipeline_state.py
├── drive_archive.py
├── rag.py
├── uploads/
├── pipeline_states/
├── embedding_work/
├── db_sync/
└── data/
    └── knowledge.db
```

---

# 🚀 Quick Start

```bash
git clone https://github.com/YOUR-USER/Research-Knowledge-Backend.git
cd Research-Knowledge-Backend

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

python3 -m uvicorn api_v08:app \
  --host 127.0.0.1 \
  --port 8010
```

Check status:

```bash
curl http://127.0.0.1:8010/v08/status
```

---

# ☁️ Google Drive Integration

The reference implementation uses a Google Drive folder named:

```text
KnowledgBase
```

The DGX host accesses Drive through an authenticated `rclone` remote.

Never commit:

```text
rclone.conf
OAuth credentials
client_secret
access tokens
refresh tokens
```

to GitHub.

---

# 🌐 Deployment

```text
Next.js
   │
   ▼
Vercel
   │
   ▼
Cloudflare
   │
   ▼
FastAPI on local GPU infrastructure
```

Example frontend environment variable:

```env
KNOWLEDGE_API_URL=https://knowledge-api.example.org
```

---

# 🔒 Security

Before deploying this system for a larger team, consider adding:

- authentication,
- user accounts,
- role-based permissions,
- API keys,
- upload size limits,
- MIME validation,
- rate limiting,
- Cloudflare Access,
- request auditing,
- encrypted backups.

Never expose Ollama, agent sandboxes or internal inference services directly to the public Internet.

---

# 🗺️ Roadmap

- [ ] Research team authentication
- [ ] Multiple research groups
- [ ] View original evidence from search
- [ ] Google Drive source links
- [ ] Multi-image packages
- [ ] Date filters
- [ ] Topic filters
- [ ] Organization filters
- [ ] Researcher/person filters
- [ ] Automatic citation extraction
- [ ] DOI detection
- [ ] arXiv detection
- [ ] GitHub repository detection
- [ ] Knowledge Graph
- [ ] Agent API / MCP interface
- [ ] Multi-agent research workflows
- [ ] WhatsApp ingestion
- [ ] Email ingestion
- [ ] Browser extension
- [ ] Research digest generation
- [ ] Duplicate evidence detection
- [ ] Collaborative annotations

---

# 🤝 Contributing

Contributions are welcome.

You can help by:

🐛 reporting bugs

🧠 proposing better retrieval strategies

🤖 integrating new vision-language models

🔌 adding new ingestion adapters

🎨 improving the frontend

🔐 strengthening security

📚 improving documentation

🔬 testing it in real research environments

🌎 translating the interface

If you use the project in your laboratory or research group, please share your experience.

---

# 🧪 Research Philosophy

### 1. Preserve the evidence
AI interpretations can change. The original source should remain available.

### 2. Structured knowledge should be regenerable
AI-generated summaries, topics and embeddings are computational products.

### 3. Research memory should belong to the research team
AI should help researchers build collective intelligence rather than create another information silo.

---

# 💡 From Information to Research Memory

```text
Images
Papers
Videos
Code
Experiments
Datasets
Messages
Conference Notes
Web Resources
        │
        ▼
 Multimodal Knowledge Layer
        │
        ▼
 Search + RAG + Agents
        │
        ▼
 Institutional Research Memory
```

A laboratory should be able to ask:

> What have we learned?

> Where did we learn it?

> Who contributed it?

> What evidence supports it?

> How does it connect to what we already know?

That is the direction of **Research Knowledge Hub**.

---

# ❤️ Build Knowledge With Your Team

Research should not be a collection of isolated memories.

Bring your students.

Bring your collaborators.

Bring your screenshots.

Bring your papers.

Bring your experiments.

Bring your questions.

Build a shared memory.

**Capture knowledge. Connect evidence. Learn together.**

🧠 + 👩‍🔬 + 👨‍🔬 + 🤖 = 🌍

---

# 📄 License

MIT License.

See `LICENSE` for the complete license text.

---

# ⭐ Support the Project

If you find the project useful:

⭐ Star the repository  
🍴 Fork it  
🧪 Test it with your research team  
🔧 Improve it  
📣 Share it with another laboratory  
🤝 Contribute back  

**The more teams that contribute knowledge and ideas, the more useful this infrastructure can become.**

---

## 🧠 Research Knowledge Hub

### From scattered evidence to collective intelligence.
