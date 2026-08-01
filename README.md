# PawPal+ Agentic Scheduler

## Original Project

This project extends **PawPal+**, my Module 2 CodePath AI110 project. The
original PawPal+ was a Streamlit app that let a pet owner track care tasks
(walks, feeding, meds, grooming) for multiple pets and generate a daily
schedule based on task priority and available time. It used four core
classes, `Owner`, `Pet`, `Task`, and `Scheduler`, with a greedy algorithm
that sorted tasks by priority and filled the owner's time budget.

## Summary

The original PawPal+ scheduler was purely algorithmic: it applied one fixed
rule (priority, then duration) with no sense of which outcomes actually
mattered to a pet owner, like never skipping a medication. This project adds
an **agentic review layer** on top of that scheduler. A `ScheduleAgent`
checks each generated plan against stated constraints and, if it finds a
violation, tells the scheduler exactly which task to force back in, then
re-checks. This loop repeats until the plan passes review or a safety cap is
hit, turning a one-shot algorithm into a system that plans, checks its own
work, and corrects itself.

## Architecture Overview

See `diagrams/architecture.mmd` for the full diagram. At a high level:

1. An `Owner` with `Pet`s and `Task`s feeds into `Scheduler.generate_plan()`,
   which produces a candidate plan using the original greedy algorithm.
2. `ScheduleAgent` reviews that plan against a small set of stated
   constraints (e.g. "meds tasks must never be skipped"). This can run in
   `mock` mode (deterministic rules, no API needed) or `live` mode (real
   reasoning via the Gemini API).
3. If the agent finds a violation, it returns `force_include_ids`, the
   specific tasks that must be scheduled to fix the problem. The scheduler
   regenerates the plan with those tasks locked in, and the loop repeats,
   capped at 3 iterations so it can never run forever.
4. Once approved (or the cap is reached), the final plan is logged to
   `ai_interactions.md` and displayed to the user.
5. A separate `Reliability Harness` (`eval_harness.py`) runs this entire
   loop against 4 predefined synthetic scenarios and reports a pass/fail and
   confidence summary, independent of any single live demo run.

Humans stay in the loop in two places: the constraints the agent checks
against are ones I defined, not learned, and I reviewed every reasoning
trace in `ai_interactions.md` by hand before treating this as working
correctly.

## Setup Instructions
```
    git clone https://github.com/YOUR_USERNAME/agentic-scheduler.git
    cd agentic-scheduler
    pip install -r requirements.txt

    # Run the core demo
    python main.py

    # Run the agentic reliability harness (mock mode, no API key needed)
    python eval_harness.py --mode mock

    # Run the full test suite
    python -m pytest
```
Optional, to see real LLM reasoning instead of the rule-based mock reviewer:

    # 1. Get a free key at https://aistudio.google.com/apikey
    # 2. $env:GEMINI_API_KEY="your_key_here"   (PowerShell)
    # 3. python eval_harness.py --mode live

Note: the Gemini free tier caps `gemini-3.5-flash` at 20 requests/day, so
live mode is meant for occasional verification, not repeated runs.

## Reproducible Execution Evidence

### Reliability harness (mock mode)
```
    python eval_harness.py --mode mock

    ======================================================================
    PawPal+ ScheduleAgent Reliability Report
    ======================================================================
    Scenario            Iterations  Approved  Confidence  Sched/Skip
    ----------------------------------------------------------------------
    meds_conflict       2           True      1.0         1/1
    ignored_pet         2           True      1.0         2/1
    no_violations       1           True      1.0         2/0
    impossible_budget   3           False     0.6         0/1
    ----------------------------------------------------------------------
    3/4 scenarios ended in an approved plan.
    Average final confidence: 0.90

    Note: 'impossible_budget' is expected to remain unapproved, since no
    amount of reordering can fit a 10-minute mandatory task into a 5-minute
    budget. The agent correctly stops at max_iterations instead of looping
    forever trying to force the impossible.
```

### Reliability harness (live mode, real Gemini 3.5 Flash reasoning)
```
    python eval_harness.py --mode live

    ======================================================================
    PawPal+ ScheduleAgent Reliability Report
    ======================================================================
    Scenario            Iterations  Approved  Confidence  Sched/Skip
    ----------------------------------------------------------------------
    meds_conflict       2           True      1.0         1/1
    ignored_pet         2           True      1.0         2/1
    no_violations       1           True      1.0         2/0
    impossible_budget   3           False     1.0         0/1
    ----------------------------------------------------------------------
    3/4 scenarios ended in an approved plan.
    Average final confidence: 1.00
```
Live mode matched mock mode's pass/fail pattern exactly, confirming the
agent reasons correctly about the same constraints mock mode only checks by
hardcoded rule. One limitation worth naming: every scenario returned
confidence exactly 1.0, which likely means the agent isn't meaningfully
distinguishing its own uncertainty across different situations rather than
being right every time. A more calibrated confidence signal would be a
natural next improvement.

### Core PawPal+ test suite
```
    python -m pytest

    ========================================================== test session starts ===========================================================
    platform win32 -- Python 3.14.5, pytest-9.0.3, pluggy-1.6.0
    collected 15 items

    tests\test_pawpal.py ..........                                                                                                     [100%]
    tests\test_agent.py .....                                                                                                           [100%]

    =========================================================== 15 passed in 0.09s ===========================================================
```

## Sample Interactions

### 1. Correcting a skipped meds task

**Setup:** A dog has a low-priority meds task and a longer high-priority
playtime task, with only 30 minutes available. The greedy scheduler alone
skips the meds task in favor of the longer, higher-priority one.

**Agent output (live Gemini 3.5 Flash):**
```
    {
      "approved": false,
      "issues": [
        "A task in the 'meds' category ('ddc8b68b' for Biscuit) was skipped.",
        "Pet 'Biscuit' has zero scheduled tasks today despite having an incomplete task."
      ],
      "force_include_ids": ["ddc8b68b"],
      "confidence": 1.0
    }
```
The agent identified both the specific rule violation and the exact task ID
needed to fix it, using only the plain-English constraint list, no
hardcoded logic tells it what "meds" means.

### 2. Reordering to include a second pet's task

**Setup:** One pet has two high-priority tasks (Walk, Feed) that alone
consume the full 30-minute budget in the greedy sort order. A second pet's
lower-priority task (Litter) gets skipped entirely, leaving that pet with
nothing scheduled.

**Iteration 1 — agent flags the problem:**
```
    {
      "approved": false,
      "issues": ["Pet 'Whiskers' has at least one incomplete task today but zero scheduled tasks."],
      "force_include_ids": ["55490d38"],
      "confidence": 1.0
    }
```
**Iteration 2 — after forcing Litter in, the plan now covers both pets and passes review:**
```
    {
      "approved": true,
      "issues": [],
      "force_include_ids": [],
      "confidence": 1.0
    }
```
Forcing the smaller task in first freed enough time for one of the dog's
two tasks (Feed) to still fit, so both pets ended up covered, just not with
every original task included.

### 3. Recognizing an unsolvable constraint (and a real limitation)

**Setup:** A meds task takes 10 minutes, but only 5 minutes are available
today. No reordering can make it fit.

The agent correctly never approves this plan across all 3 iterations:
```
    Iteration 1: {"approved": false, "issues": [meds skipped, zero scheduled], "force_include_ids": ["daf73774"], "confidence": 1.0}
    Iteration 2: {"approved": false, "issues": [same two, reworded], "force_include_ids": ["daf73774"], "confidence": 1.0}
    Iteration 3: {"approved": false, "issues": [same two, reworded again], "force_include_ids": ["daf73774"], "confidence": 1.0}
```

**Limitation worth noting:** the agent's response is nearly identical
across all three iterations, it has no memory of having already suggested
the same fix and watched it fail to resolve anything. It re-evaluates from
scratch each time rather than recognizing "I said this last iteration and
nothing changed, this is unsolvable." The system still behaves safely
(`max_iterations` stops it from looping forever, and it correctly reports
`approved: false`), but a more sophisticated version would detect this
stall condition explicitly instead of repeating the same suggestion.

## Design Decisions

I built the agent to operate through a single, narrow interface:
`force_include_ids`, a list of task IDs the scheduler must include before
anything else. This keeps the greedy algorithm itself untouched and
auditable, the agent doesn't rewrite scheduling logic, it just tells the
existing scheduler which tasks matter more than the algorithm alone would
guess. The tradeoff is that the agent can only fix problems solvable by
reordering. It can't invent a shorter version of a task or expand the
available time budget, so a genuinely impossible constraint correctly stays
unresolved rather than the agent fabricating a fix.

I built a mock mode alongside the live Gemini mode specifically so testing
and grading don't depend on network access, an API key, or daily quota
limits. The mock reviewer checks the same constraints a human would want
checked, just through explicit rules instead of an LLM's judgment.

I originally built this against `gemini-2.5-flash`, which returned a 404
partway through development, Google retired it for new API keys ahead of
its full shutdown on October 16, 2026. I migrated to `gemini-3.5-flash`,
the current free-tier model, and confirmed matching results.

On API failure (including the rate-limit exhaustion documented in
`ai_interactions.md`), the system falls back to `approved: true,
confidence: 0.0` rather than crashing. This favors availability over strict
correctness: the owner always gets a usable plan, even if the review itself
couldn't run. The downside, observed directly during testing, is that a
truly invalid plan can get silently approved if the API fails at the wrong
moment. See `model_card.md` for the full discussion of this tradeoff.

## Testing Summary

15/15 automated tests pass: 10 from the original PawPal+ system
(`tests/test_pawpal.py`) and 5 for the new agent (`tests/test_agent.py`).
The reliability harness (`eval_harness.py`) runs 4 synthetic scenarios
covering a skipped mandatory task, a pet left out of the plan entirely, an
already-valid plan, and a genuinely unsolvable time budget, in both mock
and live mode, with matching pass/fail outcomes in both. One test scenario
initially failed during development for a reason worth documenting: my
first draft of `ignored_pet` demanded 45 minutes of tasks against a
30-minute budget, mathematically unsolvable regardless of order. That
wasn't an agent bug, it was an unfair test; fixing the scenario's numbers
resolved it, a good reminder to verify a test case is solvable before
treating a failure as a defect.

**Confidence level:** ★★★★☆ (4/5). Core logic is solid and independently
verified in both mock and live mode. The star deducted reflects two
observed, real limitations: uncalibrated confidence scores (always exactly
1.0 in live mode) and the API-failure fallback silently approving an
invalid plan during an actual rate-limit event.

## UI 

### Adding tasks:
![Task Scheduling](<Screenshot 2026-08-01 112921.png>)

### Mock mode:
![Fails to accurately schedule tasks, ignoring important tasks](<Screenshot 2026-08-01 111118.png>)

### Agentic Scheduler
![Live mode on](<Screenshot 2026-08-01 111159.png>)
![](<Screenshot 2026-08-01 111224.png>)


## Stretch Goals Attempted

### Agentic Workflow Enhancement
`log_agent_interactions.py` runs the full plan → review → correct loop
across 3 scenarios and saves every intermediate reasoning step, not just
the final answer, to `ai_interactions.md`. Each entry includes the exact
plan the scheduler proposed and the agent's full structured review of it.

### Test Harness / Evaluation Script
`eval_harness.py` runs the agent against 4 predefined synthetic scenarios
and prints a pass/fail/confidence summary table (see above). It supports
both `--mode mock` and `--mode live`, so the same evaluation logic checks
both the rule-based and LLM-based reviewers.

## Reflection

My graded reflection on AI collaboration, limitations, biases, and system
tradeoffs is in [`model_card.md`](./model_card.md), per the assignment's
requirement that reflection content live there rather than here.