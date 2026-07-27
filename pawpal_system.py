from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from datetime import date, timedelta
import uuid


PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Task:
    name: str
    category: str
    duration_minutes: int
    priority: str
    scheduled_time: Optional[str] = None  # "HH:MM" 24-hour format
    frequency: Optional[str] = None  # "daily", "weekly", or None for one-off
    recurring: bool = False
    completed: bool = False
    due_date: date = field(default_factory=date.today)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def mark_complete(self):
        """Marks this task as completed."""
        self.completed = True

    def reset(self):
        """Resets a recurring task back to incomplete for the next day."""
        if self.recurring:
            self.completed = False

    def next_occurrence(self) -> Optional["Task"]:
        """Returns a new Task instance for the next occurrence if this task
        has a frequency set, or None for one-off tasks."""
        if self.frequency == "daily":
            delta = timedelta(days=1)
        elif self.frequency == "weekly":
            delta = timedelta(weeks=1)
        else:
            return None

        return Task(
            name=self.name,
            category=self.category,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            scheduled_time=self.scheduled_time,
            frequency=self.frequency,
            recurring=self.recurring,
            completed=False,
            due_date=self.due_date + delta,
        )


@dataclass
class Pet:
    name: str
    species: str
    breed: str
    tasks: List[Task] = field(default_factory=list)
    owner: Optional["Owner"] = None

    def add_task(self, task: Task):
        """Adds a new task to this pet's task list."""
        self.tasks.append(task)

    def remove_task(self, task_id: str):
        """Removes a task from this pet's task list by its unique id."""
        self.tasks = [t for t in self.tasks if t.id != task_id]

    def get_tasks(self) -> List[Task]:
        """Returns this pet's current list of tasks."""
        return self.tasks

    def complete_task(self, task_id: str) -> Optional[Task]:
        """Marks a task complete and, if it recurs, adds its next occurrence.
        Returns the newly created task, or None if there isn't one."""
        task = next((t for t in self.tasks if t.id == task_id), None)
        if task is None:
            return None

        task.mark_complete()
        next_task = task.next_occurrence()
        if next_task:
            self.add_task(next_task)
        return next_task


@dataclass
class Owner:
    name: str
    available_minutes: int = 0
    pets: List[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet):
        """Adds a pet to this owner and links the pet back to the owner."""
        pet.owner = self
        self.pets.append(pet)

    def set_available_minutes(self, minutes: int):
        """Sets how many minutes the owner has available for tasks today."""
        self.available_minutes = minutes

    def get_all_tasks(self) -> List[Tuple[Pet, Task]]:
        """Flattens tasks across all pets, paired with their owning pet."""
        all_tasks = []
        for pet in self.pets:
            for task in pet.get_tasks():
                all_tasks.append((pet, task))
        return all_tasks


class Scheduler:
    def __init__(self, owner: Owner):
        """Builds a scheduler for a given owner and their pets."""
        self.owner = owner

    def collect_tasks(self) -> List[Tuple[Pet, Task]]:
        """Pulls all incomplete tasks across the owner's pets."""
        return [
            (pet, task)
            for pet, task in self.owner.get_all_tasks()
            if not task.completed
        ]

    def sort_by_priority(
        self, tasks: List[Tuple[Pet, Task]]
    ) -> List[Tuple[Pet, Task]]:
        """Sorts tasks by priority first, then by duration as a tiebreaker."""
        return sorted(
            tasks,
            key=lambda pt: (PRIORITY_ORDER.get(pt[1].priority, 99), -pt[1].duration_minutes),
        )

    def sort_by_time(
        self, tasks: List[Tuple[Pet, Task]]
    ) -> List[Tuple[Pet, Task]]:
        """Sorts tasks chronologically by scheduled_time (HH:MM). Tasks with
        no scheduled time are placed at the end."""
        return sorted(
            tasks,
            key=lambda pt: pt[1].scheduled_time or "23:59",
        )

    def filter_tasks(
        self,
        tasks: List[Tuple[Pet, Task]],
        pet_name: Optional[str] = None,
        completed: Optional[bool] = None,
    ) -> List[Tuple[Pet, Task]]:
        """Filters tasks by pet name and/or completion status. Either filter
        is skipped if left as None."""
        result = tasks
        if pet_name is not None:
            result = [(pet, task) for pet, task in result if pet.name == pet_name]
        if completed is not None:
            result = [(pet, task) for pet, task in result if task.completed == completed]
        return result

    def filter_by_time(
        self, tasks: List[Tuple[Pet, Task]]
    ) -> Tuple[List[Tuple[Pet, Task]], List[Tuple[Pet, Task]]]:
        """Greedily fits tasks into the owner's time budget, returning (scheduled, skipped)."""
        scheduled = []
        skipped = []
        remaining = self.owner.available_minutes

        for pet, task in tasks:
            if task.duration_minutes <= remaining:
                scheduled.append((pet, task))
                remaining -= task.duration_minutes
            else:
                skipped.append((pet, task))

        return scheduled, skipped

    def sort_by_priority_then_time(
        self, tasks: List[Tuple[Pet, Task]]
    ) -> List[Tuple[Pet, Task]]:
        """Sorts tasks by priority first, then chronologically within each
        priority tier. Combines sort_by_priority and sort_by_time for a
        single ordering that reflects both urgency and time of day."""
        return sorted(
            tasks,
            key=lambda pt: (
                PRIORITY_ORDER.get(pt[1].priority, 99),
                pt[1].scheduled_time or "23:59",
            ),
        )

    def find_next_available_slot(
        self, tasks: List[Tuple[Pet, Task]], duration_minutes: int,
        day_start: str = "07:00", day_end: str = "21:00",
    ) -> Optional[str]:
        """Finds the earliest HH:MM slot of at least duration_minutes that
        doesn't overlap any already-scheduled task, within the given day
        window. Returns None if no such slot exists. Uses a simple linear
        scan over sorted scheduled intervals rather than an interval tree,
        since a single day's task list is small enough not to need one."""

        def to_minutes(hhmm: str) -> int:
            h, m = map(int, hhmm.split(":"))
            return h * 60 + m

        def to_hhmm(total_minutes: int) -> str:
            return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"

        busy = sorted(
            (to_minutes(t.scheduled_time), to_minutes(t.scheduled_time) + t.duration_minutes)
            for _, t in tasks
            if t.scheduled_time is not None
        )

        cursor = to_minutes(day_start)
        end_of_day = to_minutes(day_end)

        for start, end in busy:
            if start - cursor >= duration_minutes:
                return to_hhmm(cursor)
            cursor = max(cursor, end)

        if end_of_day - cursor >= duration_minutes:
            return to_hhmm(cursor)

        return None

    def detect_conflicts(self, tasks: List[Tuple[Pet, Task]]) -> List[str]:
        """Lightweight conflict check: flags tasks that share the same
        scheduled_time, since the owner can't physically do two things at
        once. Returns a list of human-readable warning strings, never raises."""
        warnings = []
        by_time = {}
        for pet, task in tasks:
            if task.scheduled_time is None:
                continue
            by_time.setdefault(task.scheduled_time, []).append((pet, task))

        for time_slot, group in by_time.items():
            if len(group) > 1:
                names = ", ".join(f"{pet.name}: {task.name}" for pet, task in group)
                warnings.append(f"Conflict at {time_slot} — {names}")

        return warnings

    def generate_plan(
        self, force_include_ids: Optional[List[str]] = None
    ) -> Tuple[List[Tuple[Pet, Task]], List[Tuple[Pet, Task]]]:
        """Runs collect, sort, then filter in that fixed order. If force_include_ids is given, those tasks are scheduled first
        (consuming time budget before anything else), letting an external
        reviewer (like an agent) correct a specific violation without
        re-deriving the whole plan from scratch."""
        tasks = self.collect_tasks()
        force_include_ids = force_include_ids or []

        forced = [pt for pt in tasks if pt[1].id in force_include_ids]
        rest = [pt for pt in tasks if pt[1].id not in force_include_ids]

        sorted_rest = self.sort_by_priority(rest)
        ordered = forced + sorted_rest
        return self.filter_by_time(ordered)