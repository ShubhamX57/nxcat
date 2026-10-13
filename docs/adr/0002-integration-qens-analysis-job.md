# 2. Integration: a qens analysis job, not a SciCat push (for now)

Status: accepted · Date: 2026-10-13

## Context

nxcat needed one integration with another system. The two candidates were:

- **SciCat push:** register each ingested dataset in a local SciCat, the catalogue
  ESS runs. Very relevant to ESS, but SciCat needs several services (backend,
  MongoDB, authentication) to run locally, which is a large setup for a small project.
- **qens analysis job:** run a fit from [qens](https://github.com/ShubhamX57/qens), a
  QENS analysis library, on a dataset, and store the result with the dataset. This
  links data, analysis and provenance, the same loop a facility catalogue supports.

## Decision

Build the qens analysis job.

- `POST /api/v1/datasets/{id}/analyses` (login required) queues a run and returns
  202. A background task calls qens: `read_nxspe_with_overrides` → `fit_elastic_peak`
  → `extract_hwhm`, then fits Fickian diffusion (`fickian_hwhm`) to Γ(Q) to give D.
- Every run is stored in an `analysis` table with its settings, result or error, the
  qens version **and source commit** (read from the installed package), the nxcat
  version, who started it and when.
- qens is pinned to an exact commit in `uv.lock`, so a result can be tied to code.
- The synthetic QENS files use the NXSPE layout qens reads, record the instrument
  resolution, and store the true D, so the analysis can be checked against it.

## What we learned

The resolution matters most. With the instrument resolution recorded in the file,
D was recovered within about 1–2%. When the resolution was estimated from the
dataset's own elastic peak (which the quasi-elastic signal widens), D came out about
15% high, because low-Q bins have the narrowest lines and the smallest error bars.
nxcat therefore prefers, in order: a resolution given in the request, then the one
recorded in the file, and only then the estimate, with a warning in the result.

## Consequences

- Background tasks run inside the API process: a restart loses a queued run. A real
  service would use a job queue. Acceptable for a demonstration.
- Only Fickian diffusion is offered. qens has more models (Chudley-Elliott,
  Singwi-Sjölander, rotations, Bayesian MCMC); adding them is a matter of new methods.
- A SciCat push remains a good next integration, recorded as a "later" item.
