# ADR 0001 Versioned workspace store

**Status:** Accepted for the first persistent workspace slice  
**Date:** 2026-10-17

## Context

CLARVIO must keep customer evidence, decisions, draft plans, and approvals connected without letting a later draft overwrite an approved commitment. The first release starts with a small local deployment and no employee system integration. Ticket 13 needs durable workspace creation now and a data model that later tickets can extend through migrations.

## Decision

Use SQLite for the initial deployment, with numbered SQL migrations. A `Workspace` is the stable container. Every accepted plan mutation appends an immutable `PlanVersion` snapshot and advances the workspace's `current_version` in the same transaction. Repeated requests return their recorded response when the idempotency key and request fingerprint match. A stale expected version or reused key with different content fails with a conflict.

The first migration creates `workspaces`, `plan_versions`, and `idempotency_keys`. Future migrations add the other domain records when their vertical slices are built. Snapshots remain the audit source for a plan version even if later tables provide indexed views of requirements or tasks. Approval will refer to one exact, immutable plan version.

## Logical data model

| Entity | Relationship and ownership | Version rule |
| --- | --- | --- |
| Workspace | Stable customer request container; owns sources, messages, and plan versions. | Points to its latest version. |
| Source | Uploaded file or pasted brief in one workspace. | Stable source ID; extracted text and metadata remain available to evidence links. |
| Message | Customer or assistant turn in one workspace. | Append-only conversation evidence. |
| Requirement | Claim in a plan version, supported by one or more source or message references. | Confirmation belongs to a version. |
| Assumption | Proposed condition in a plan version, explicitly approved or rejected by the customer. | Decision belongs to a version. |
| PlanVersion | Snapshot of scope, plan status, tasks, timeline, and conditions within a workspace. | Append-only; `(workspace_id, version)` is unique. |
| Task | Proposed work in a plan version; can depend on other tasks and link to requirements. | Edits produce a new plan version. |
| Assignment | Suggested task owner and rationale based on a versioned employee dataset. | Belongs to the task and plan version. |
| Approval | Manager, time, and exact approved plan version. | The approved version is immutable; changes branch into a later draft. |

Evidence links must resolve to a source passage or customer message in the same workspace. Employee profiles and workload data are a separate planning input; the first release marks them as mock data. Manager and customer identities and access checks are added in ticket 1.

## Initial physical contract

- `workspaces`: stable ID, name, status, current version, creation and update times.
- `plan_versions`: composite workspace/version key, status, JSON snapshot, creation time, future actor reference. Rows are inserted and never updated by the application.
- `idempotency_keys`: operation scope and key, request hash, and exact saved response. Reusing a key for different input is a conflict.
- `schema_migrations`: applied migration versions. A new schema change is a new numbered migration; old migrations are not edited after deployment.

The initial screen stores a name and short request summary in each snapshot. This gives the versioning path a customer-visible behavior before documents and tasks are introduced.

## Consequences

SQLite keeps local setup simple and supports transactional writes and restart tests. It suits a small single-instance pilot. Before a multi-instance deployment, evaluate a server database and move through a migration plan while preserving the plan-version contract. The database file contains customer content once document intake ships, so deployment must add backups, access controls, retention rules, and encryption appropriate to that environment.
