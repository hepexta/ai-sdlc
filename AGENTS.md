# AGENTS.md — ai-sdlc

Rules for agents working in this repository.

## Issue size limit

**Every issue file under `.scratch/*.md` must be ≤ 500 lines.** Target 300–450. This applies to issue files only; `README.md` and `TEMPLATE.md` are exempt.

The issue is the readable entry point, not the full design archive. It must contain the problem, the user prompt, the runtime inputs, the key plan, the blocking questions, and links to the detail.

If an issue would exceed 500 lines:

1. Move the detailed design to the project's `docs/` (for example `code-review-bot/docs/PLAN.md`) or `.scratch/<slug>/spec.md`.
2. Leave a one-line summary and a relative link in the issue.
3. Never delete a requirement to hit the limit. Relocate it.
4. Re-count before finishing.

Windows:

```powershell
(Get-Content .scratch\0001-code-review-bot.md).Count
```

Git Bash / Linux:

```bash
wc -l .scratch/0001-code-review-bot.md
```

A 500+ line issue is a split signal, not a formatting problem.

## Issue structure

- One issue per file, `NNNN-<slug>.md`; never combine issues.
- Keep the six sections in order: **Description, User Prompt, Context, Plan, Open Questions, Notes**.
- `## User Prompt` must include a concise `### User Inputs` table for runtime parameters, with secrets represented as file paths/references only.
- Open Questions keeps only blocking/near-term decisions; put the full list in a linked doc.
- Detail docs may be longer, but must have a clear title, status, and back-link to the issue.

## Secrets

- Never write a secret value into an issue, doc, manifest, commit, or command line.
- Record the source path (Vault), delivery mechanism (ESO/ExternalSecret), consuming file (`*_FILE`), and rotation owner.
- Follow `code-review-bot/docs/SECRETS.md`.

## User-facing text

- If the work emits comments, notifications, or reports, define the voice with a good/bad example and a lint or review bar.
- Human-like means natural prose, not impersonation; keep the bot identity visible.
- Follow `code-review-bot/docs/COMMENT_STYLE.md` for the review bot.

## Verification before calling an issue done

- [ ] Issue file ≤ 500 lines.
- [ ] Links resolve locally.
- [ ] Status and labels agree (`Draft` / `In Progress` / `In Review` / `Done`).
- [ ] No secret values in any file.
- [ ] Acceptance evidence is linked from Notes.
