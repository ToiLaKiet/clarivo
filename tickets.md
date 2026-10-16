| # | Ticket | Blocked by | What it delivers |
|---|---|---|---|
| 13 | Persistent workspace and plan data model | None | A customer can create and reopen a durable, versioned workspace; the database model and migrations establish the records used by later features. |
| 01 | Workspace and role access | 13 | A customer can access only their workspace; a manager can access review actions. |
| 02 | Document intake | 01 | A customer can upload or paste a brief and see readable source text, with clear errors for unsupported files. |
| 03 | Evidence-linked clarification chat | 02 | AI asks focused questions and proposes requirements linked to source passages or customer messages. |
| 04 | Requirement and assumption decisions | 03 | The customer confirms requirements, approves or rejects assumptions, and explicitly confirms scope. |
| 05 | Employee capacity directory | 01 | A manager can see the skills, availability, and existing workload used for planning. |
| 06 | Task and effort proposal | 04 | Confirmed scope becomes reviewable tasks with acceptance criteria, dependencies, and effort ranges. |
| 07 | Balanced employee allocation | 05, 06 | Each task gets a qualified suggested owner; uneven usage and unassignable work are visible. |
| 08 | Capacity-aware timeline | 07 | Tasks receive working-day dates that respect dependencies and employee capacity. |
| 09 | Manager review and approval | 08 | A manager edits and approves one exact plan version; conflicts block approval. |
| 10 | Approved task-file export | 09 | The approved plan downloads as CSV and JSON, including owners, effort, dates, and traceability. |
| 11 | Google Sheets delivery | 10 | An approved task list can be sent to a chosen sheet without duplicate rows on retry. |
| 12 | Jira delivery | 10 | An approved task list can be created in a chosen Jira project without duplicate issues on retry. |
