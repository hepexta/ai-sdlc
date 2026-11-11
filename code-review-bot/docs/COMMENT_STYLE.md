# Comment voice

**Status:** Planning design for [issue 0001](../../.scratch/0001-code-review-bot.md). Not implemented yet.

## Goal

Write like a senior engineer leaving a PR comment — not like a report generator.

The bot account remains visibly a bot. "Human-like" means natural, direct prose, not a claim of human authorship, fake personal experience, or concealed automation.

## Rules for inline comments

1. **Start with the problem**, not a severity badge, heading, or "I noticed".
2. **One issue per comment.** Two short paragraphs at most.
3. **Say what breaks, for whom, under what conditions.** Then say how to fix it.
4. **Use plain, direct language.** Contractions are fine. Avoid corporate/AI vocabulary.
5. **Vary the opening.** Do not reuse the same template for every finding.
6. **No report formatting inside inline comments:** no `##` headings, no bold labels such as `**Why:**`, no bullet lists unless the fix genuinely has ordered steps.
7. **No emojis.** No praise inflation. No "great catch" unless it is specific and true.
8. **No visible model/confidence/run metadata.** Keep machine markers in hidden HTML comments only.
9. **Code identifiers in backticks.** Quote only the line or expression that matters.
10. **If unsure, say so plainly:** "I'm not sure this handles X — can you confirm?" Do not invent certainty.
11. **Do not claim tests pass, code compiles, or a fix works** unless the bot actually verified it.
12. **Keep it short:** target ≤ 120 words; hard cap 160. Word count excludes the optional suggestion block.

## Severity without badges

Express severity through the consequence and a short natural phrase:

- **Critical / blocking:** "This needs to be fixed before merge." / "This lets any authenticated user read another customer's order."
- **Major / should fix:** "Worth fixing before merge." / "This will fail when the list is empty."
- **Minor / not blocking:** "Not blocking, but..." / "Small thing: ..."
- **Question:** "I'm not sure this covers X — can you confirm?"

The structured severity stays in the hidden marker and the summary grouping.

## Good and bad examples

### Critical security issue

Bad:

> **Critical · security** — Broken access control in order lookup
>
> **Why:** The repository call does not compare the order owner to the caller.
> **Evidence:** `orderRepository.findById(id)`.
> **Suggested fix:** Add an ownership check.
> **Confidence:** 0.93 · run 0f5c9c1e

Good:

> `findById` returns any customer's order, not just the caller's. Any authenticated user can read someone else's order by changing the ID.
>
> Load it by id and customer id, or check ownership before returning the DTO. A 403 test would cover the regression.

### Major correctness issue

Bad:

> **Major · correctness** — Potential NoSuchElementException
>
> This code uses `Optional.get()` without checking `isPresent()`. Consider using `orElseThrow()`.

Good:

> `findByEmail` returns an empty `Optional` for unknown addresses, so this `get()` throws for a normal "user not found" path.
>
> Use `orElseThrow(() -> new UserNotFound(email))` and map that to a 404. Worth a test for the unknown-email case.

### Minor issue

Bad:

> **Minor · maintainability** — Consider extracting a helper for readability.

Good:

> Not blocking, but this retry block is now duplicated in two handlers. If the backoff changes again, both need the same edit. Extracting the retry policy would keep them together.

### Question instead of a false claim

Bad:

> This is wrong and will fail in production.

Good:

> I'm not sure this handles a null `customerId` — the controller allows it through. Can you confirm the validation happens earlier?

## Forbidden AI tells

The style linter should reject these in visible comment text:

- "As an AI", "as a language model", "I hope this helps"
- "I noticed that", "it appears that", "it seems that"
- "comprehensive", "robust", "leverage", "delve", "seamless", "cutting-edge"
- "Let's dive in", "here's a breakdown", "in conclusion", "overall"
- "This code is", "the code snippet", "the provided code"
- Visible "Confidence:", "Run ID:", "Model:", "Tokens:" in an inline comment
- Markdown headings (`^#`) and bold-label scaffolding (`**Why:**`, `**Evidence:**`, `**Fix:**`)
- Emojis and severity badges at the start of the comment

Some of these words are legitimate in technical prose; the linter targets repeated framing, not a single use in a sentence.

## Summary voice

The sticky summary should read like a short handoff, not a dashboard:

```markdown
## Review

The order lookup is the main problem: any authenticated customer can read another customer's order by changing the ID. The retry path itself looks solid.

**Blocking**
- `OrderController.java:64` — ownership check missing

**Worth fixing**
- `UserService.java:87` — `Optional.get()` throws for unknown emails

Not ready to merge until the ownership check is fixed; the rest can follow up.

<sub>16 found → 5 accepted / 9 rejected / 1 downgraded / 1 added · 7 posted · 105,400 tokens · effort medium/high/high · `AI Reviewed` added</sub>
```

Rules:

- A short prose lead, then the smallest useful grouping.
- Metrics live in a compact footer, not at the top.
- No "ship_with_fixes" robot verdict in the prose; say what a reviewer would say.
- The hidden marker still records the machine verdict (`ship`, `ship_with_fixes`, `do_not_ship`).

## Machine markers

Inline comments keep hidden markers for idempotency and evaluation:

```html
<!-- crb:f:<fingerprint> severity=critical -->
```

No visible `confidence`, `model`, `run_id`, or `tokens` in the comment body. Those belong in `/out/review.json` and the summary footer.

## Lint and evaluation

Deterministic style checks:

- Word count ≤ 120 target / 160 hard cap.
- No `^#` headings, no visible `**...**` scaffolding, no emoji.
- No forbidden AI-tell phrases.
- No visible confidence/model/run/token metadata.
- No identical first five words across more than 30% of comments.
- At most one short list; prefer prose.

Human review sample:

- Blind-sample 20 posted comments.
- Rate naturalness 1–5 and "would a human reviewer write this?" yes/no.
- Target: average ≥ 4.0 and ≥ 80% "human-like".
- Review a paired sample of human comments to keep the bar honest.

## Non-goals

- Pretending the bot is a human.
- Inventing personal anecdotes ("when I worked on...").
- Hiding automation or the `AI Reviewed` label.
- Adding praise or small talk to seem friendly.
- Making comments longer to sound thorough.
