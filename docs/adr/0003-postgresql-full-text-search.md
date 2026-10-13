# 3. PostgreSQL full-text search instead of a search engine

Status: accepted · Date: 2026-10-13

## Context

Users search by structured filters (instrument, technique, temperature, dates) and by
free text (title, sample name, instrument). The usual options for free text are a
search engine such as Elasticsearch or OpenSearch, or the full-text search built into
PostgreSQL. nxcat is expected to hold thousands of datasets, not millions.

## Decision

Use PostgreSQL full-text search.

- `dataset.search_vector` is a generated `tsvector` column over title, sample name and
  instrument, so it can never be out of date with the row.
- A GIN index on that column keeps text search fast.
- Queries use `websearch_to_tsquery`, which accepts anything a person types (quotes,
  `or`, `-word`) without a syntax error.
- Structured filters are ordinary indexed SQL conditions in the same query.

## Consequences

- One service fewer to run, secure, back up and keep in sync. Filters and text search
  happen in one query and one transaction.
- English stemming works ("benzenes" finds "benzene"), but there is no fuzzy matching
  for typos and no relevance tuning beyond PostgreSQL's ranking.
- **When to change:** with millions of records, heavy faceting across many fields, or a
  need for typo tolerance and per-field boosting, a search engine would be the better
  choice. The API would stay the same: only `api/search.py` would change.
