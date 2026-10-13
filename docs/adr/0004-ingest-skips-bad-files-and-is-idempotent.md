# 4. Ingest skips bad files and can be run again safely

Status: accepted · Date: 2026-10-13

## Context

Real data folders contain files that are truncated, not HDF5 at all, missing required
fields, or holding impossible values (an end time before the start time). Folders are
also ingested again and again as new runs arrive. A scientist should never have to
clean a folder by hand before nxcat will read it.

## Decision

1. **A bad file is recorded and skipped.** The reason is stored in `ingest_error` and
   printed, and the run carries on with the next file.
2. **A database problem stops the run.** It is not the file's fault, and carrying on
   would only record hundreds of misleading file errors.
3. **Ingest is idempotent.** Files are matched by their path. Each file's SHA-256
   checksum is compared with the stored one: if it is the same, the file is not read
   again (`unchanged`); if it differs, the row is updated in place (`updated`), using
   PostgreSQL's `INSERT ... ON CONFLICT DO UPDATE`.
4. **Metadata is validated before it is stored**, by the same pydantic model
   (`DatasetMetadata`) that the synthetic generator uses, so valid test files are valid
   by construction.

## Consequences

- One broken file never blocks a folder of good ones, and the report says exactly
  which files failed and why.
- Running ingest twice gives the same database, so it is safe to run on a schedule.
- Checksums mean a changed file is noticed even if its name is the same.
- Hashing reads every file once per run. For very large folders, a cheaper first check
  (file size and modification time) could skip the hash for files that clearly have not
  changed.
- A file that is deleted from disk stays in the catalogue. Removing or flagging missing
  files would be a separate, deliberate step.
