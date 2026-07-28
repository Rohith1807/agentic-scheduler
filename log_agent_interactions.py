"""
Logs real agentic reasoning traces to ai_interactions.md.

This exists specifically for the "Agentic Workflow Enhancement" stretch
goal, which asks for intermediate reasoning traces from a multi-step agent
saved to ai_interactions.md, not just a final answer. Each run below is a
distinct scenario, and each iteration within a run is logged: the plan the
scheduler proposed, and the agent's full review of it, including cases
where the agent's own suggestion didn't resolve anything (see the
impossible_budget scenario) and cases where it took multiple corrections
to reach an approved plan.

Usage:
    python log_agent_interactions.py --mode mock   # no API key needed
    python log_agent_interactions.py --mode live    # real Gemini reasoning
"""

import argparse
from datetime import datetime

from pawpal_system import Owner, Pet, Task
from agent import run_agentic_loop


LOG_PATH = "ai_interactions.md"


def scenario_meds_conflict():
    owner = Owner(name="Test Owner A")
    owner.set_available_minutes(30)
    dog = Pet(name="Biscuit", species="Dog", breed="Golden Retriever")
    owner.add_pet(dog)
    dog.add_task(Task(name="Meds", category="meds", duration_minutes=10, priority="low"))
    dog.add_task(Task(name="Playtime", category="enrichment", duration_minutes=25, priority="high"))
    return owner


def scenario_ignored_pet():
    owner = Owner(name="Test Owner B")
    owner.set_available_minutes(30)
    dog = Pet(name="Biscuit", species="Dog", breed="Golden Retriever")
    cat = Pet(name="Whiskers", species="Cat", breed="Tabby")
    owner.add_pet(dog)
    owner.add_pet(cat)
    dog.add_task(Task(name="Walk", category="walk", duration_minutes=20, priority="high"))
    dog.add_task(Task(name="Feed", category="feed", duration_minutes=15, priority="high"))
    cat.add_task(Task(name="Litter", category="grooming", duration_minutes=12, priority="low"))
    return owner


def scenario_impossible_budget():
    owner = Owner(name="Test Owner D")
    owner.set_available_minutes(5)
    dog = Pet(name="Biscuit", species="Dog", breed="Golden Retriever")
    owner.add_pet(dog)
    dog.add_task(Task(name="Meds", category="meds", duration_minutes=10, priority="high"))
    return owner


SCENARIOS = {
    "meds_conflict": scenario_meds_conflict,
    "ignored_pet": scenario_ignored_pet,
    "impossible_budget": scenario_impossible_budget,
}


def main(mode: str):
    with open(LOG_PATH, "a") as f:
        f.write(f"\n---\n\n# Agentic Run Log — {datetime.now().isoformat(timespec='seconds')} ({mode} mode)\n")

    for name, builder in SCENARIOS.items():
        owner = builder()
        with open(LOG_PATH, "a") as f:
            f.write(f"\n## Scenario: {name}\n")

        run_agentic_loop(owner, mode=mode, max_iterations=3, log_path=LOG_PATH)

    print(f"Logged {len(SCENARIOS)} scenario run(s) to {LOG_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Log agentic reasoning traces to ai_interactions.md")
    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    args = parser.parse_args()
    main(args.mode)