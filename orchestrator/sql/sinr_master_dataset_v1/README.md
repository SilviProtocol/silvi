# SINR Master Dataset v1 SQL Blueprint

Status: design-only SQL, not yet executed

This folder contains the first-pass SQL blueprint for the SINR master dataset layout.

Goals:

- create new canonical master tables without mutating legacy tables,
- create release registry tables,
- make future strict-full rebuilds auditable,
- and prepare for immutable train/serving releases.

Files:

- `master_dataset_blueprint.sql` - commented DDL / CTAS skeletons

Important:

- This blueprint is intentionally conservative.
- It should be reviewed against live BigQuery schemas before execution.
- It does not drop, overwrite, or mutate existing legacy SINR tables.
