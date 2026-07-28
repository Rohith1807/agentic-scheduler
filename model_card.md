# Model Card: PawPal+ ScheduleAgent

## What it does
Reviews algorithmically-generated pet care schedules against a small set of
stated constraints and corrects violations by forcing specific tasks into
the plan, iterating up to 3 times.

## Limitations and biases
- Constraints are hardcoded (meds priority, per-pet coverage), not learned
  or user-configurable.
- Mock mode only catches the exact violations it was written to check for.
- **Observed, not hypothetical:** during live testing, the free tier's
  20-requests/day quota for `gemini-3.5-flash` was exhausted mid-run,
  triggering the API failure fallback in `_review_live`. The fallback
  returned `approved: true, confidence: 0.0` for a plan that should have
  stayed unapproved (a mandatory meds task was still unscheduled). This is
  a real instance of a tradeoff I'd already anticipated in design: the
  system favors never crashing over never being wrong, and on this occasion
  that meant silently passing an actually-invalid plan. A more careful
  version would return a distinct status like `"review_unavailable"`
  instead of collapsing an API failure into `approved: true`, so the owner
  isn't misled into thinking the plan was actually checked.

## Could this be misused?
Low risk. The worst outcome from a bad agent decision is a poorly ordered
pet-care schedule, not a decision with real safety stakes. The main risk is
over-trusting the "approved" flag, since mock mode's approval only reflects
the handful of rules it explicitly checks.

## What surprised me during testing
My first version of the "ignored_pet" reliability scenario failed on every
iteration. I initially assumed it was an agent bug. Tracing through it
showed the scenario itself demanded more total task-minutes than the
available time budget, so no reordering could ever satisfy it. Useful
reminder to verify a test scenario is solvable before treating a failure as
a defect.

## AI collaboration

**A genuinely helpful suggestion:** The `force_include_ids` design was the
most useful architectural suggestion I got. Early on, my first instinct for
the agent correction loop was to have it directly rewrite or reorder the
scheduler's output. The AI pushed back on that and suggested a narrower
interface instead: the agent only ever returns which specific task IDs must
be included, and the existing `Scheduler.generate_plan()` decides how to
fit them in. I verified this was the right call once I saw it in practice,
it meant the original greedy algorithm from Module 2 never had to change at
all, and every correction the agent makes is traceable to one specific,
auditable decision rather than a black-box rewrite of the whole plan.

**A flawed suggestion I had to catch myself:** When we first wired up
`gemini-2.5-flash`, everything looked fine on paper, the code ran, the
prompt was reasonable. It wasn't until I actually ran `eval_harness.py
--mode live` that I got a 404 saying the model was no longer available to
new users. That wasn't something the AI could have caught without me
actually running it against a live API key, since it doesn't have a live
connection to test against itself. I had to be the one to report the exact
error message back before we could find the actual current model name
(`gemini-3.5-flash`) and fix it. It was a good reminder that AI-suggested
code that looks complete and reasonable still has to be run for real before
I can trust it, especially anything touching an external API that changes
on its own schedule.

**How I verified things rather than just accepting them:** The clearest
example was the `ignored_pet` test scenario. My first version of it failed
on every single run, and my first assumption was that the agent's logic had
a bug. Instead of accepting that read, I traced through the actual numbers
by hand and found the scenario itself demanded 45 minutes of tasks against
a 30-minute budget, which is unsolvable no matter what order you schedule
things in. The "bug" was in my test data, not the agent. That distinction
mattered: if I'd just accepted "the agent is broken" at face value, I'd
have started changing correct code to fix a test that was never fair to
begin with.

**Separate chat sessions, one continuous build:** Working through this
project phase by phase, design, implementation, testing, then the agentic
layer, meant each conversation stayed focused on one layer of the system
instead of me re-explaining the whole project's context every time. It also
meant that when something broke (like the encoding issue that mangled
em-dashes in `ai_interactions.md` on Windows), I could isolate it to
exactly the piece of code responsible rather than searching through
unrelated logic.