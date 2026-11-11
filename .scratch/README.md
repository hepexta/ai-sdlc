# AI-SDLC Issue Tracker

Local-first issue tracking for projects under `C:\Work\Projects\AI\ai-sdlc`.

This folder is the source of truth for **what we intend to build, why, and how far it has progressed**. It is deliberately plain Markdown: greppable, diffable, reviewable, and usable offline. No external tracker is required.

The conventions adapt Matt Pocock's local-markdown issue tracker (`.scratch/<feature>/`) and the planning flow from `C:\Work\Projects\AI\mattpocock-skills`: **grill → spec → tickets → implement → code review**. See [How this maps to the skills](#how-this-maps-to-the-matt-pocock-skills).

---

## Layout

```
.scratch/
├── README.md                 # this file — conventions, labels, workflow, index
├── TEMPLATE.md               # canonical issue template (six sections)
├── NNNN-<slug>.md            # intake issue, one file per intent
├── research/                 # dated, cited research dossiers
│   └── YYYY-MM-DD-<topic>.md
├── decisions/                # optional ADRs (one decision per file)
│   └── NNNN-<slug>.md
└── <slug>/                   # optional detail for a large issue
    ├── spec.md               # full spec when the issue outgrows one file
    └── issues/               # tracer-bullet tickets, one file per ticket
        └── 01-<slug>.md
```

Rules:

- **One issue per file.** Never combine several issues into one document.
- **Numbering is monotonic.** `0001`, `0002`, … Zero-pad to four digits. Never reuse or renumber an ID.
- **Slugs are kebab-case** and describe the outcome, not the implementation (`code-review-bot`, not `add-fastapi-endpoint`).
- **Supporting detail goes in the matching `<slug>/` folder**, so the intake issue stays readable. Link back from the issue.
- **Research is shared.** Put cross-issue research in `research/`; put issue-specific research in `<slug>/research.md`.
- **Do not delete issues.** Mark them `Done` (or add a `## Notes` entry explaining why they were abandoned).

---

## Issue metadata

Every issue starts with this block, immediately below the H1:

```markdown
**Status:** Draft
**Labels:** Draft
**Type:** Feature
**Project:** code-review-bot
**Created:** 2026-11-11
**Updated:** 2026-11-11
**Owner:** unassigned
```

- `Status` and `Labels` must agree. The status is the one state label currently applied.
- `Type` is `Feature`, `Bug`, `Chore`, or `Research`. It is not a label; it never changes the workflow state.
- `Project` is the folder name under `ai-sdlc/` that the work belongs to.
- `Owner` is a person or `unassigned`. An unassigned issue may sit in `Draft`; it may not sit in `In Progress`.
- Update `Updated` whenever the status or substantive content changes.

---

## Labels

There are exactly four workflow labels. Use these strings verbatim; later migration to GitHub Issues should create labels with the same names.

| Label | Meaning | Enter when | Exit when |
|---|---|---|---|
| `Draft` | Intent captured, still being shaped | The problem and rough solution are written down | Scope, acceptance criteria, and top open questions are settled |
| `In Progress` | Actively being implemented | Plan approved; owner assigned; first ticket started | Implementation is complete and verification has started |
| `In Review` | Awaiting review or verification | A PR / build / demo exists and needs review | Review is approved and verification evidence is recorded |
| `Done` | Complete and verified | Acceptance criteria met, evidence recorded, docs updated | Reopened only for a regression, with a note explaining why |

Rules:

1. **Exactly one workflow label per issue.** Never `Draft` + `In Progress`.
2. **No skipping `Draft`.** A hotfix may move `Draft → In Progress` in the same day, but the issue still gets a one-paragraph description, acceptance criteria, and a risk note first.
3. **Backward moves are allowed and expected.** `In Review → In Progress` when changes are requested. `Done → In Progress` only for a regression; add a `## Notes` entry with the date and reason.
4. **A label is a claim, not a wish.** Moving to `In Review` means reviewable evidence exists. Moving to `Done` means the evidence is linked.

Status flow:

```
Draft ──► In Progress ──► In Review ──► Done
              ▲               │
              └───────────────┘
               changes requested

Done ──► In Progress   (regression only, with a Notes entry)
```

---

## Required issue sections

Every issue uses [TEMPLATE.md](./TEMPLATE.md) and contains these six sections, in this order:

1. **Description** — the problem, the outcome, scope boundaries, and what success looks like.
2. **User Prompt** — the request as the user actually made it, quoted, plus a short interpretation.
3. **Context** — current state, constraints, prior art, assumptions, and links.
4. **Plan** — architecture, interfaces, milestones/tickets, acceptance criteria, validation, risks.
5. **Open Questions** — every unresolved decision, with a recommended default and impact.
6. **Notes** — research, decisions, references, glossary, changelog.

A section may be short, but it may not be omitted. "None" is a valid answer only after the question has been considered.

### Quality bar

- **Description** is understandable to someone who has not read the conversation.
- **User Prompt** preserves the original wording; interpretation is clearly separated.
- **Context** cites primary sources for external claims (links, versions, star counts with a date).
- **Plan** is testable: every milestone has a demo or verification, not just a task list. For review/quality work, name the review passes, the rejection/noise policy, and what the final gate actually checks.
- **Credentials** are described by source and delivery, never by value: the Vault/secret-manager path, the sync mechanism, and who owns rotation.
- **User-facing text has a defined voice.** If the work emits comments, notifications, or reports, include a short good/bad example and a lint or review bar; "sounds human" needs a concrete definition.
- **Open Questions** always include a default. An unanswered question must not block `Draft → In Progress` if a safe default exists.
- **Notes** records *why*, not just *what*; link decisions and alternatives.

---

## Workflow

### 1. Capture (`Draft`)

Create `.scratch/NNNN-<slug>.md` from `TEMPLATE.md`. Fill Description and User Prompt first; leave Plan rough. If the intent is vague, run a grilling session (`/grill-me` or `/grill-with-docs`) and record the answers in Context / Open Questions.

### 2. Shape (`Draft`)

Turn the intent into a spec-quality Plan:

- Identify the seams where the work will be verified.
- List tracer-bullet tickets with blocking edges (vertical slices, each demoable).
- Resolve or default every Open Question.
- Add acceptance criteria and a rollback path.

Definition of Ready for `In Progress`:

- [ ] Problem and outcome are unambiguous.
- [ ] In-scope / out-of-scope are explicit.
- [ ] Acceptance criteria are testable.
- [ ] Top open questions are resolved or have an accepted default.
- [ ] Target project folder and owner are set.
- [ ] Main risks and mitigations are listed.

### 3. Build (`In Progress`)

Work the ticket frontier: any ticket whose blockers are done. Keep the issue's Plan as the index; put detailed ticket files under `<slug>/issues/`. Record verification evidence in Notes as it happens, not at the end.

### 4. Review (`In Review`)

Run `/code-review` (two axes: **Standards** and **Spec**) and any project-specific verification. Link the PR, test output, screenshots, or benchmark results. Fix or explicitly defer every `Critical` / `Required` finding.

Definition of Done:

- [ ] Every acceptance criterion is checked with evidence.
- [ ] Review findings are resolved or deferred with a written justification.
- [ ] Tests/verification commands and results are recorded in Notes.
- [ ] Docs, README, and deployment manifests are updated.
- [ ] No open `Critical` / `Required` items remain.
- [ ] Status and labels are both `Done`; `Updated` is current.

### 5. Close (`Done`)

Move the issue to `Done`. Do not delete it. If the work is superseded, add a Notes entry with the replacement issue link.

---

## How this maps to the Matt Pocock skills

The canonical skills are in `C:\Work\Projects\AI\mattpocock-skills`. This tracker uses their **local Markdown** issue-tracker convention, with a simpler four-label state machine.

| Matt Pocock skill | Use here | Tracker effect |
|---|---|---|
| `/grill-me`, `/grill-with-docs` | Sharpen a vague intent; build shared vocabulary | Answers land in Context / Open Questions; still `Draft` |
| `/to-spec` | Synthesize the conversation into a spec | Fill Description + Plan; may move to `In Progress` once Ready |
| `/to-tickets` | Break the Plan into tracer bullets | Create `<slug>/issues/NN-*.md` with `Blocked by` |
| `/triage` | Decide whether an issue is ready, needs info, or won't be fixed | Map to `Draft` / `In Progress` / `Done`; record the reason |
| `/implement` | Build ticket by ticket with TDD | `In Progress`; evidence appended to Notes |
| `/code-review` | Two-axis review of the diff | `In Review`; findings and resolution linked |
| `/research` | Investigate against primary sources | `research/YYYY-MM-DD-<topic>.md`; cited |

Canonical triage roles map as follows:

| Canonical role | Local label |
|---|---|
| `needs-triage` | `Draft` |
| `needs-info` | `Draft` (add an Open Question) |
| `ready-for-agent` | `In Progress` |
| `ready-for-human` | `In Review` |
| `wontfix` | `Done` (Notes explains why) |

AI-generated comments or triage notes posted to an external tracker must start with `> *This was generated by AI during triage.*` per the upstream skill. Inside this local tracker, add `AI-assisted: yes` to Notes when an agent wrote substantive content.

---

## Naming and indexing

File name: `NNNN-<slug>.md`, e.g. `0001-code-review-bot.md`.

Keep the index below current whenever an issue is created or changes status.

| ID | Title | Status | Project | Updated |
|---|---|---|---|---|
| [0001](./0001-code-review-bot.md) | AI-accelerated Java/Python code review bot | Draft | code-review-bot | 2026-11-11 |

---

## Useful commands

List every issue and its status (PowerShell):

```powershell
Get-ChildItem .scratch\*.md |
  Where-Object Name -NotIn @('README.md','TEMPLATE.md') |
  Select-String -Pattern '^# |^\*\*Status:\*\*|^\*\*Labels:\*\*' |
  ForEach-Object { $_.Line }
```

Find work in a given state:

```powershell
Select-String -Path .scratch\*.md -Pattern '^\*\*Status:\*\* In Progress' -List
```

Check that Status and Labels agree:

```powershell
Get-ChildItem .scratch\*.md |
  Where-Object Name -NotIn @('README.md','TEMPLATE.md') |
  ForEach-Object {
    $s = (Select-String -Path $_.FullName -Pattern '^\*\*Status:\*\* (.+)$').Matches.Groups[1].Value
    $l = (Select-String -Path $_.FullName -Pattern '^\*\*Labels:\*\* (.+)$').Matches.Groups[1].Value
    if ($s -ne $l) { "$($_.Name): Status=$s Labels=$l" }
  }
```

---

## Ground rules

- **Evidence over assertion.** Link the command, output, PR, or benchmark that proves a claim.
- **Defaults over stalls.** If a decision cannot be made now, record the default and the date it will be revisited.
- **Small issues, vertical slices.** A ticket is done when a user-visible or verifiable behaviour works end to end.
- **No secrets in issues.** Reference secret names, never values.
- **Write for the next agent.** Assume the reader has the repo but not this conversation.
