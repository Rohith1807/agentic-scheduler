# capture_samples.py
from pawpal_system import Owner, Pet, Task
from agent import run_agentic_loop
import json

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

for name, builder in [("ignored_pet", scenario_ignored_pet), ("impossible_budget", scenario_impossible_budget)]:
    print(f"\n{'='*20} {name} {'='*20}")
    owner = builder()
    plan, skipped, trace = run_agentic_loop(owner, mode="live", max_iterations=3)
    for entry in trace:
        print(f"\n--- Iteration {entry['iteration']} ---")
        print(entry["plan_summary"])
        print("Raw reasoning:")
        print(entry["review"]["raw_reasoning"])