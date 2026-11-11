# NNNN — {Issue title}

**Status:** Draft
**Type:** Feature
**Project:** {project-slug}
**Created:** YYYY-MM-DD
**Updated:** YYYY-MM-DD
**Owner:** unassigned

<!--
Copy this file to .scratch/NNNN-{slug}.md.
Keep all six sections, in this order. Delete the guidance comments once filled.
Status and Labels must match: Draft | In Progress | In Review | Done.
See README.md for the workflow, definitions of ready/done, and label rules.
Replace every {placeholder}; leaving one in a finished issue is a smell.
-->

## User Prompt

<!--
Quote the request as it was actually made. Preserve wording, typos, and language.
Do not "clean it up" — future agents need the original intent. Then separate your
interpretation clearly.
-->

> {Verbatim user request. Use a blockquote; include the full relevant message.}

**Interpretation:**

- {What I believe the user means by ambiguous terms}
- {What I am assuming is included}
- {What I am assuming is excluded}

## Description

<!--
The problem and the outcome, from the user's perspective. Understandable without
reading the conversation. 3–8 sentences or a short bullet list.
-->

**Problem:** {What hurts today, for whom, and why now.}

**Outcome:** {What will be true when this is done.}

**In scope:**

- {Capability 1}
- {Capability 2}

**Out of scope:**

- {Explicitly excluded capability, integration, or audience}

**Success looks like:**

- {A measurable or directly observable result}
- {Another result}

## Context

<!--
Everything a fresh agent needs that is not in the codebase yet: current state,
constraints, prior art, versions, links, and assumptions.
Cite external claims with a URL and an access date.
-->

**Current state:**

- {What exists today; what is missing; where the work will live.}

**Constraints:**

- {Platform, language, deployment, budget, deadline, compliance, licensing.}

**Prior art / references:**

- [Title](URL) — {what it establishes, and why it matters here.}

**Assumptions:**

- {Assumption 1 — and what happens if it is wrong.}
- {Assumption 2}

## Plan

<!--
The approach, not a file-by-file task list. Include the seams where the work will
be verified, the interfaces that must be stable, tracer-bullet milestones with
blocking edges, acceptance criteria, validation, and rollback.
Prefer outcomes and demoable slices over horizontal layer work.
For review/quality work, add a "Review passes" table (role, model, job, output,
gate) and state the rejection/noise policy explicitly.
If the work handles credentials, name the secret source, delivery path, and
rotation owner; never write values into the issue.
If the work produces user-facing text, define its voice and include one good
and one bad example.
-->

### Approach

{2–5 paragraphs or a diagram explaining the chosen design and the key trade-offs.}

### Interfaces and contracts

| Surface | Shape | Notes |
|---|---|---|
| {CLI / API / config / event} | {Inputs, outputs, errors} | {Compatibility or versioning rule} |

### Milestones / tickets

<!--
Each row is a vertical slice: a narrow but complete path that is demoable or
verifiable on its own. "Blocked by" uses the issue/ticket numbers.
-->

| # | Deliverable (end-to-end behaviour) | Blocked by | Demo / verification |
|---|---|---|---|
| 01 | {Behaviour this slice makes work} | None | {Command, test, or demo} |
| 02 | {Behaviour} | 01 | {Evidence} |

### Acceptance criteria

- [ ] {Testable criterion 1}
- [ ] {Testable criterion 2}
- [ ] {Operational criterion: deploy, rollback, observability}

### Validation

- **Unit / contract:** {What is tested in isolation.}
- **Integration / end-to-end:** {What runs against real boundaries.}
- **Quality / performance:** {Benchmark, load, accuracy, or cost threshold.}
- **Security:** {Threats tested and controls verified.}

### Risks and rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| {Risk} | Low/Med/High | Low/Med/High | {Prevention or detection} |

**Rollback:** {How to disable or revert safely, and what data/state is affected.}

## Open Questions

<!--
Every unresolved decision gets a row. A question without an answer must still have
a safe default so work is not blocked. Mark the few that genuinely must be decided
before In Progress. Delete rows once resolved, or record the resolution in Notes.
-->

| ID | Question | Default if unanswered | Impact if wrong | Needed by |
|---|---|---|---|---|
| Q1 | {Decision that is still open} | {Safe default} | {What changes if the default is wrong} | Draft / In Progress |
| Q2 | {Decision} | {Default} | {Impact} | {Milestone} |

## Notes

<!--
Research findings, decisions and their rationale, alternatives considered,
glossary, and a dated changelog. Link, don't paste, where possible.
-->

### Research

- [Dossier or source](URL) — {finding, date, version/star snapshot.}

### Decisions

| Date | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| YYYY-MM-DD | {Decision} | {Why} | {What else was considered} |

### Glossary

- **{Term}** — {project-specific meaning; avoid synonyms.}

### Changelog

- **YYYY-MM-DD** — {What changed in this issue and why.}
