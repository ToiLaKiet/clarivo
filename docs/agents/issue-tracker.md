# Issue tracker: GitHub

Issues and specs for this repo live in GitHub Issues at ToiLaKiet/clarivo.
Use the `gh` CLI from this repository for issue operations.

## Conventions

- Create issues with `gh issue create`; put multiline bodies in a file and pass `--body-file`.
- Read an issue and comments with `gh issue view <number> --json number,title,body,labels,comments`.
- List open work with `gh issue list --state open`; filter by labels when needed.
- Use `gh issue comment`, `gh issue edit`, and `gh issue close` for updates.
- Publish blocking edges as native GitHub issue dependencies when available.
  Resolve each blocker's database ID, then add it to the dependent issue's
  `dependencies/blocked_by` endpoint. If dependencies are unavailable, place
  `Blocked by: #<number>` in the dependent issue body.
- When a skill says to publish a ticket, create a GitHub issue. When it says
  to fetch a ticket, read the issue body and comments.

## Pull requests as a triage surface

PRs as a request surface: no.

## Wayfinding

Use one issue labelled `wayfinder:map` as the map and link child tickets as
sub-issues when supported. Record blocking edges as described above.
