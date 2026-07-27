# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:

```bash
==================================================
Today's Schedule for Rohith
Available time: 60 minutes
==================================================
1. [HIGH  ] Biscuit    Morning walk         (30 min)
2. [HIGH  ] Biscuit    Feeding              (10 min)
3. [MEDIUM] Whiskers   Litter box cleaning  (15 min)

Total time used: 55/60 minutes

Skipped (not enough time today):
  - Whiskers: Playtime (20 min)
==================================================
```

## 🧪 Testing PawPal+

Run the full test suite:

    python -m pytest

These tests cover:
- **Sorting correctness** — tasks are returned in chronological order by scheduled time, with unscheduled tasks placed last
- **Filtering** — by pet name and by completion status
- **Recurrence logic** — completing a daily task automatically creates the next day's occurrence, one-off tasks do not
- **Conflict detection** — two tasks scheduled at the same time are flagged with a warning, without crashing the program
- **Edge case** — a pet with zero tasks doesn't break sorting or filtering

```bash
========================================================== test session starts ===========================================================
platform win32 -- Python 3.14.5, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\Users\rohit\OneDrive - University of St. Thomas\codepath\ai110-module2show-pawpal-starter
plugins: anyio-4.13.0
collected 10 items                                                                                                                        

tests\test_pawpal.py ..........                                                                                                     [100%]

=========================================================== 10 passed in 0.06s ===========================================================
```
Confidence Level - ★★★★


## 📐 Smarter Scheduling

| Feature           | Method(s)                          | Notes                                                        |
| ------------------ | ----------------------------------- | ------------------------------------------------------------- |
| Task sorting       | `Scheduler.sort_by_priority()`, `Scheduler.sort_by_time()` | Priority sort tiebreaks on duration; time sort treats unscheduled tasks as end-of-day |
| Filtering          | `Scheduler.filter_tasks()`          | Filters by pet name and/or completion status independently |
| Conflict handling  | `Scheduler.detect_conflicts()`      | Exact time-match detection only, does not catch overlapping durations |
| Recurring tasks    | `Task.next_occurrence()`, `Pet.complete_task()` | Daily/weekly frequency, uses `timedelta` to compute next due date |

## ✨ Features

- **Multi-pet support** — one owner can manage multiple pets, each with their own task list
- **Priority-based scheduling** — `Scheduler.generate_plan()` fills the owner's available time with the highest-priority tasks first
- **Time-based sorting** — `Scheduler.sort_by_time()` orders tasks chronologically, with unscheduled tasks placed last
- **Filtering** — `Scheduler.filter_tasks()` filters by pet or by completion status
- **Conflict warnings** — `Scheduler.detect_conflicts()` flags tasks scheduled at the exact same time so the owner can catch double-booking before the day starts
- **Daily and weekly recurrence** — `Task.next_occurrence()` automatically generates the next instance of a recurring task when the current one is marked complete

## 📸 Demo Walkthrough

1. The owner enters their name and how many minutes they have available today.
2. The owner adds one or more pets by name and species.
3. For each pet, the owner adds care tasks with a title, duration, priority, scheduled time, and frequency (one-time, daily, or weekly).
4. The app displays all tasks sorted by time, with a filter to view a single pet's tasks or hide completed ones.
5. If two tasks share the same scheduled time, a warning appears immediately, naming both tasks and the conflicting time.
6. The owner clicks "Generate schedule." The Scheduler sorts remaining tasks by priority and fills the available time budget, showing which tasks made the cut and which were skipped for lack of time.
7. The owner can mark any task complete. If it's a daily or weekly task, the next occurrence is created automatically and its due date is shown.


## Setup Instructions

    git clone https://github.com/YOUR_USERNAME/agentic-scheduler.git
    cd agentic-scheduler
    pip install -r requirements.txt

    # Run the core demo
    python main.py

    # Run the agentic reliability harness (mock mode, no API key needed)
    python eval_harness.py --mode mock

    # Run the full test suite
    python -m pytest

    # Optional: live mode with real Gemini calls
    # 1. Get a free key at https://aistudio.google.com/apikey
    # 2. export GEMINI_API_KEY=your_key_here
    # 3. python eval_harness.py --mode live

## Testing Summary

5/5 automated tests for the ScheduleAgent pass (`tests/test_agent.py`),
alongside the 10 tests from the core PawPal+ system (`tests/test_pawpal.py`),
for 15/15 total. The reliability harness (`eval_harness.py`) runs 4 synthetic
scenarios covering: a skipped mandatory task, a pet left out of the plan
entirely, an already-valid plan, and a genuinely unsolvable time budget.

    ======================================================================
    PawPal+ ScheduleAgent Reliability Report
    ======================================================================
    Scenario            Iterations  Approved  Confidence  Sched/Skip
    ----------------------------------------------------------------------
    meds_conflict       2           True      1.0         1/1
    ignored_pet         2           True      1.0         2/1
    already_fine        1           True      1.0         2/0
    impossible_budget   3           False     0.6         0/1
    ----------------------------------------------------------------------

    3/4 scenarios ended in an approved plan.
    Average final confidence: 0.90

One test scenario initially failed for a reason worth documenting: my first
draft of the "ignored_pet" scenario demanded 45 minutes of tasks against a
30-minute budget, which is mathematically unsolvable regardless of task
order. That wasn't an agent bug, it was an unfair test. Fixing the
scenario's numbers (so the correct reordering actually fits) resolved it,
which is a good reminder to sanity-check whether a test case is solvable
before treating a failure as a defect.

## Design Decisions

I built the agent to operate through a single, narrow interface:
`force_include_ids`, a list of task IDs the scheduler must include before
anything else. This keeps the greedy algorithm itself untouched and
auditable, the agent doesn't rewrite scheduling logic, it just tells the
existing scheduler which tasks matter more than the algorithm alone would
guess. The tradeoff is that the agent can only fix problems solvable by
reordering. It can't invent a shorter version of a task or change the
available time budget, so a genuinely impossible constraint (see
`impossible_budget` above) correctly stays unresolved rather than the agent
fabricating a fix.

I also built a mock mode alongside the live Gemini mode specifically so
testing and grading don't depend on network access or an API key. The mock
reviewer checks the same constraints a human would want checked, just
through explicit rules instead of an LLM's judgment.

### Live mode (real Gemini 3.5 Flash reasoning)

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

One limitation worth naming: every scenario returned confidence exactly
1.0, which doesn't necessarily mean the agent is right every time, just
that it's not meaningfully distinguishing its own uncertainty across
different situations. A more calibrated confidence signal would be a
natural next improvement.

## Sample Interactions

### 1. Correcting a skipped meds task

**Setup:** A dog has a low-priority meds task and a longer high-priority
playtime task, with only 30 minutes available. The greedy scheduler alone
skips the meds task in favor of the longer, higher-priority one.

**Agent output (live Gemini 3.5 Flash):**

    {
      "approved": false,
      "issues": [
        "A task in the 'meds' category ('ddc8b68b' for Biscuit) was skipped.",
        "Pet 'Biscuit' has zero scheduled tasks today despite having an incomplete task."
      ],
      "force_include_ids": ["ddc8b68b"],
      "confidence": 1.0
    }

The agent identified both the specific rule violation and the exact task ID
needed to fix it, using only the plain-English constraint list, no
hardcoded logic tells it what "meds" means.

### 2. Reordering to include a second pet's task

**Setup:** One pet has two high-priority tasks (Walk, Feed) that alone
consume the full 30-minute budget in the greedy sort order. A second pet's
lower-priority task (Litter) gets skipped entirely, leaving that pet with
nothing scheduled.

**Iteration 1 — agent flags the problem:**

    {
      "approved": false,
      "issues": ["Pet 'Whiskers' has at least one incomplete task today but zero scheduled tasks."],
      "force_include_ids": ["55490d38"],
      "confidence": 1.0
    }

**Iteration 2 — after forcing Litter in, the plan now covers both pets and passes review:**

    {
      "approved": true,
      "issues": [],
      "force_include_ids": [],
      "confidence": 1.0
    }

Forcing the smaller task in first freed enough time for one of the dog's
two tasks (Feed) to still fit, so both pets ended up covered, just not with
every original task included.

### 3. Recognizing an unsolvable constraint (and a real limitation)

**Setup:** A meds task takes 10 minutes, but only 5 minutes are available
today. No reordering can make it fit.

The agent correctly never approves this plan across all 3 iterations,
confirming it doesn't rubber-stamp an impossible situation just to end the
loop:

    Iteration 1: {"approved": false, "issues": [... meds skipped ..., ... zero scheduled ...], "force_include_ids": ["daf73774"], "confidence": 1.0}
    Iteration 2: {"approved": false, "issues": [... same two issues, reworded ...], "force_include_ids": ["daf73774"], "confidence": 1.0}
    Iteration 3: {"approved": false, "issues": [... same two issues, reworded again ...], "force_include_ids": ["daf73774"], "confidence": 1.0}

**Limitation worth noting:** the agent's response is nearly identical
across all three iterations, it has no memory of having already suggested
the same fix and watched it fail to resolve anything. It re-evaluates from
scratch each time rather than recognizing "I said this last iteration and
nothing changed, this is unsolvable." The system still behaves safely
(`max_iterations` stops it from looping forever, and it correctly reports
`approved: false` rather than lying), but a more sophisticated version
would detect this stall condition and report it explicitly instead of
repeating the same unproductive suggestion three times.