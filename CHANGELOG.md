# Changelog

All notable changes to nxcat. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and version numbers follow [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-15

First release.

### Added

- **Ingest** of NeXus/HDF5 files with metadata validation. Bad files are recorded and
  skipped, and running ingest again only updates files that changed.
- **Synthetic data generator**, including deliberately broken files for testing and
  QENS files in the NXSPE layout that qens reads.
- **REST API** (FastAPI, `/api/v1`, OpenAPI docs): search with filters, paging and
  full-text search, facets, dataset details and a quick-look preview.
- **Web app** (React + TypeScript): search page with filters kept in the URL, and a
  dataset page with metadata and a quick-look plot.
- **Plain-English search**: a language model may only propose a validated filter,
  which the user confirms before it runs. Evaluated on 30 fixed questions.
- **Admin login** (JWT) for write actions: starting an ingest and starting analyses.
- **qens analysis job**: fits a Fickian diffusion coefficient to a QENS dataset in the
  background and stores the result with its settings and software versions.
- At start-up, analyses left unfinished by a previous API process are marked as failed,
  so they never stay "running" for ever.
- Docker Compose for the whole stack, and GitHub Actions CI with backend, front-end and
  end-to-end Docker checks.
- Documentation: architecture page, four design-decision records, limitations,
  contributing guide, screenshots and a demo GIF.

[0.1.0]: https://github.com/ShubhamX57/nxcat/releases/tag/v0.1.0
