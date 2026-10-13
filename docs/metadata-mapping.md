# Metadata mapping

How each field in nxcat's `dataset` table is filled. Paths follow the standard
NeXus `NXentry` layout. ISIS files use `/raw_data_1/` instead of `/entry/`.

> QENS files also hold their S(2θ, ω) data in the NXSPE layout that qens reads
> (`/entry/data/{data, error, energy, polar}` and `/entry/NXSPE_info/fixed_energy`).
> `test_qens_files_follow_the_nxspe_layout_that_qens_reads` checks this.

## Fields read from the file

The schema for these fields is `DatasetMetadata` in `backend/src/nxcat/models/metadata.py`.

| Field | Type | NeXus path | Required | Rule |
|---|---|---|---|---|
| title | str | `/entry/title` | yes | not empty |
| instrument | str | `/entry/instrument/name` | yes | stored upper-case, e.g. `LET` |
| technique | enum | `/entry/definition` | yes | one of QENS, INS, SANS, DIFFRACTION, REFLECTOMETRY, IMAGING; looked up from the instrument if `definition` doesn't say |
| run_number | int | `/entry/entry_identifier` | yes | ≥ 0 |
| sample_name | str | `/entry/sample/name` | yes | not empty |
| start_time | datetime | `/entry/start_time` | yes | ISO 8601 with a timezone |
| end_time | datetime | `/entry/end_time` | no | missing for a run still in progress; never before start_time |
| sample_temperature_k | float | `/entry/sample/temperature` | no | > 0, in kelvin; ingest converts other units using the `units` attribute |
| facility | str | `/entry/instrument/source/name` | no | |
| proposal_id | str | `/entry/experiment_identifier` | no | |

## Fields created by nxcat

| Field | How |
|---|---|
| id | database primary key |
| file_path | path given to the ingest command |
| checksum | SHA-256 of the file bytes |
| file_size_bytes | from the file system |
| schema_version | `SCHEMA_VERSION` constant (currently "1") |
| ingested_at | time of ingest, UTC |
| search_vector | PostgreSQL full-text vector built from title, sample_name and instrument |
