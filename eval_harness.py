"""
Reliability harness for the PawPal+ ScheduleAgent.

Runs the agentic loop against a set of predefined synthetic scenarios and
reports pass/fail plus confidence for each, so the agent's behavior can be
evaluated without watching a live demo. Defaults to mock mode so this is
reproducible without an API key; pass mode='live' to test against the real
Gemini calls.
"""

import argparse
from pawpal_system import Owner, Pet, Task
from agent import CONSTRAINTS, run_agentic_loop


def scenario_meds_conflict():
    """A low-priority meds task loses to a longer high-priority task under
    the greedy algorithm alone. The agent should force-include the meds task."""
    owner = Owner(name="Test Owner A")
    owner.set_available_minutes(30)
    dog = Pet(name="Biscuit", species="Dog", breed="Golden Retriever")
    owner.add_pet(dog)
    dog.add_task(Task(name="Meds", category="meds", duration_minutes=10, priority="low"))
    dog.add_task(Task(name="Playtime", category="enrichment", duration_minutes=25, priority="high"))
    return owner


def scenario_ignored_pet():
    """Two high-priority tasks for one pet consume the budget in the order
    the greedy sort picks them, leaving no room for another pet's task.
    Reordering (forcing the other pet's smaller task in first) makes room
    for everyone. The agent should find this reordering."""
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


def scenario_already_fine():
    """A plan with no constraint violations. The agent should approve it on
    the first pass without forcing any changes."""
    owner = Owner(name="Test Owner C")
    owner.set_available_minutes(60)
    dog = Pet(name="Biscuit", species="Dog", breed="Golden Retriever")
    owner.add_pet(dog)
    dog.add_task(Task(name="Meds", category="meds", duration_minutes=10, priority="high"))
    dog.add_task(Task(name="Walk", category="walk", duration_minutes=30, priority="high"))
    return owner


def scenario_impossible_budget():
    """Available time is too small to fit even the mandatory meds task. The
    agent should not loop forever trying to force something that can't fit."""
    owner = Owner(name="Test Owner D")
    owner.set_available_minutes(5)
    dog = Pet(name="Biscuit", species="Dog", breed="Golden Retriever")
    owner.add_pet(dog)
    dog.add_task(Task(name="Meds", category="meds", duration_minutes=10, priority="high"))
    return owner


SCENARIOS = {
    "meds_conflict": scenario_meds_conflict,
    "ignored_pet": scenario_ignored_pet,
    "already_fine": scenario_already_fine,
    "impossible_budget": scenario_impossible_budget,
}


def run_all(mode: str = "mock", max_iterations: int = 3):
    results = []
    for name, builder in SCENARIOS.items():
        owner = builder()
        plan, skipped, trace = run_agentic_loop(owner, mode=mode, max_iterations=max_iterations)
        final_review = trace[-1]["review"]

        results.append({
            "scenario": name,
            "iterations_used": len(trace),
            "final_approved": final_review["approved"],
            "final_confidence": final_review["confidence"],
            "scheduled_count": len(plan),
            "skipped_count": len(skipped),
        })

    return results


def print_report(results):
    print("=" * 70)
    print("PawPal+ ScheduleAgent Reliability Report")
    print("=" * 70)
    print(f"{'Scenario':<20}{'Iterations':<12}{'Approved':<10}{'Confidence':<12}{'Sched/Skip'}")
    print("-" * 70)
    for r in results:
        print(
            f"{r['scenario']:<20}{r['iterations_used']:<12}"
            f"{str(r['final_approved']):<10}{r['final_confidence']:<12}"
            f"{r['scheduled_count']}/{r['skipped_count']}"
        )
    print("-" * 70)

    passed = sum(1 for r in results if r["final_approved"])
    total = len(results)
    avg_confidence = sum(r["final_confidence"] for r in results) / total
    print(f"\n{passed}/{total} scenarios ended in an approved plan.")
    print(f"Average final confidence: {avg_confidence:.2f}")
    print(
        "\nNote: 'impossible_budget' is expected to remain unapproved, since "
        "no amount of reordering can fit a 10-minute mandatory task into a "
        "5-minute budget. The agent correctly stops at max_iterations "
        "instead of looping forever trying to force the impossible."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PawPal+ agent reliability tests.")
    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    args = parser.parse_args()

    results = run_all(mode=args.mode)
    print_report(results)