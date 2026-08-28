# Changelog

## 2026-08-28 — Images + PDF milestone

This milestone intentionally freezes ingestion scope at images and born-digital PDF papers while the architecture is stabilized.

### Added

- Specialized `pdf-researcher` path.
- Deterministic PDF inspection with PyMuPDF.
- Compact PDF evidence builder.
- PDF-to-common-evidence adapter.
- Automatic retry when the PDF agent emits invalid JSON.
- Preservation of raw agent responses for diagnosis.
- PDF support in the common research ingestion architecture.
- Persistent Google Drive archival with sequence-safe filenames.
- Resume behavior from the `saved` stage.

### Validated

A real IEEE research paper was ingested end-to-end and reached:

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

### Architecture decision

The project will remain focused on **images + PDFs** for this milestone. Other source types are intentionally deferred until these two pipelines are mature.
