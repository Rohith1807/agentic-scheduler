from pawpal_system import Owner, Pet, Task
from agent import ScheduleAgent

owner = Owner(name="Debug")
owner.set_available_minutes(30)
pet = Pet(name="Biscuit", species="Dog", breed="Golden Retriever")
owner.add_pet(pet)
pet.add_task(Task(name="Meds", category="meds", duration_minutes=10, priority="low"))

agent = ScheduleAgent(mode="live")
plan = []
skipped = [(pet, pet.tasks[0])]
result = agent.review_plan(plan, skipped)
print(result.raw_reasoning)