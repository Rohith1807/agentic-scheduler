import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pawpal_system import Owner, Pet, Task
from agent import ScheduleAgent, run_agentic_loop


def make_owner(minutes):
    owner = Owner(name="Test Owner")
    owner.set_available_minutes(minutes)
    return owner


def test_agent_approves_a_plan_with_no_violations():
    owner = make_owner(60)
    pet = Pet(name="Biscuit", species="Dog", breed="Golden Retriever")
    owner.add_pet(pet)
    pet.add_task(Task(name="Meds", category="meds", duration_minutes=10, priority="high"))
    pet.add_task(Task(name="Walk", category="walk", duration_minutes=30, priority="high"))

    plan, skipped, trace = run_agentic_loop(owner, mode="mock", max_iterations=3)

    assert trace[0]["review"]["approved"] is True
    assert len(trace) == 1
    assert len(skipped) == 0


def test_agent_flags_and_corrects_a_skipped_meds_task():
    owner = make_owner(30)
    pet = Pet(name="Biscuit", species="Dog", breed="Golden Retriever")
    owner.add_pet(pet)
    pet.add_task(Task(name="Meds", category="meds", duration_minutes=10, priority="low"))
    pet.add_task(Task(name="Playtime", category="enrichment", duration_minutes=25, priority="high"))

    plan, skipped, trace = run_agentic_loop(owner, mode="mock", max_iterations=3)

    assert trace[0]["review"]["approved"] is False
    assert any("Meds" in issue for issue in trace[0]["review"]["issues"])

    scheduled_names = [t.name for _, t in plan]
    assert "Meds" in scheduled_names


def test_agent_stops_at_max_iterations_on_impossible_constraint():
    owner = make_owner(5)
    pet = Pet(name="Biscuit", species="Dog", breed="Golden Retriever")
    owner.add_pet(pet)
    pet.add_task(Task(name="Meds", category="meds", duration_minutes=10, priority="high"))

    plan, skipped, trace = run_agentic_loop(owner, mode="mock", max_iterations=3)

    assert len(trace) == 3
    assert trace[-1]["review"]["approved"] is False


def test_agent_ensures_every_pet_gets_at_least_one_task_when_possible():
    owner = make_owner(30)
    dog = Pet(name="Biscuit", species="Dog", breed="Golden Retriever")
    cat = Pet(name="Whiskers", species="Cat", breed="Tabby")
    owner.add_pet(dog)
    owner.add_pet(cat)
    dog.add_task(Task(name="Walk", category="walk", duration_minutes=20, priority="high"))
    dog.add_task(Task(name="Feed", category="feed", duration_minutes=15, priority="high"))
    cat.add_task(Task(name="Litter", category="grooming", duration_minutes=12, priority="low"))

    plan, skipped, trace = run_agentic_loop(owner, mode="mock", max_iterations=3)

    scheduled_pets = {pet.name for pet, _ in plan}
    assert "Biscuit" in scheduled_pets
    assert "Whiskers" in scheduled_pets


def test_review_result_confidence_is_between_zero_and_one():
    agent = ScheduleAgent(mode="mock")
    owner = make_owner(10)
    pet = Pet(name="Biscuit", species="Dog", breed="Golden Retriever")
    owner.add_pet(pet)
    pet.add_task(Task(name="Meds", category="meds", duration_minutes=20, priority="high"))

    plan = []
    skipped = [(pet, pet.tasks[0])]
    result = agent.review_plan(plan, skipped)

    assert 0.0 <= result.confidence <= 1.0