import streamlit as st
from pawpal_system import Owner, Pet, Task, Scheduler
from agent import run_agentic_loop

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to PawPal+, a pet care planning assistant. Add your pets and their
care tasks below, then generate a schedule based on how much time you have today.
"""
)

with st.expander("Scenario", expanded=False):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.
"""
    )

st.divider()

# --- Session state: Owner persists across reruns ---
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan")

owner = st.session_state.owner

st.subheader("Owner")
owner.name = st.text_input("Owner name", value=owner.name)
minutes = st.number_input(
    "Available time today (minutes)",
    min_value=0,
    max_value=600,
    value=owner.available_minutes or 60,
    step=5,
)
owner.set_available_minutes(minutes)

st.divider()

# --- Add a pet ---
st.subheader("Add a pet")
col1, col2 = st.columns(2)
with col1:
    pet_name = st.text_input("Pet name", value="Mochi")
with col2:
    species = st.selectbox("Species", ["dog", "cat", "other"])

if st.button("Add pet"):
    if pet_name:
        new_pet = Pet(name=pet_name, species=species, breed="")
        owner.add_pet(new_pet)
        st.success(f"Added {pet_name}.")
    else:
        st.warning("Give your pet a name first.")

if not owner.pets:
    st.info("No pets yet. Add one above.")

st.divider()

# --- Add tasks to a specific pet ---
if owner.pets:
    st.subheader("Tasks")
    st.caption("Pick a pet, then add a task for them.")

    pet_names = [p.name for p in owner.pets]
    selected_pet_name = st.selectbox("Pet", pet_names)
    selected_pet = next(p for p in owner.pets if p.name == selected_pet_name)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        task_title = st.text_input("Task title", value="Morning walk")
    with col2:
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
    with col3:
        priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)
    with col4:
        scheduled_time = st.text_input("Time (HH:MM)", value="08:00")

    frequency = st.selectbox("Frequency", ["one-time", "daily", "weekly"])

    if st.button("Add task"):
        if task_title:
            new_task = Task(
                name=task_title,
                category="general",
                duration_minutes=int(duration),
                priority=priority,
                scheduled_time=scheduled_time or None,
                frequency=None if frequency == "one-time" else frequency,
                recurring=frequency != "one-time",
            )
            selected_pet.add_task(new_task)
            st.success(f"Added '{task_title}' to {selected_pet.name}.")

    # --- Sorted, filterable task view ---
    st.markdown("### All tasks (sorted by time)")
    scheduler = Scheduler(owner)
    all_tasks = owner.get_all_tasks()

    filter_pet = st.selectbox("Filter by pet", ["All pets"] + pet_names)
    show_completed = st.checkbox("Show completed tasks", value=True)

    filtered = scheduler.filter_tasks(
        all_tasks,
        pet_name=None if filter_pet == "All pets" else filter_pet,
        completed=None if show_completed else False,
    )
    sorted_tasks = scheduler.sort_by_time(filtered)

    if sorted_tasks:
        rows = [
            {
                "time": t.scheduled_time or "unscheduled",
                "pet": p.name,
                "task": t.name,
                "duration_min": t.duration_minutes,
                "priority": t.priority,
                "completed": "✅" if t.completed else "⬜",
            }
            for p, t in sorted_tasks
        ]
        st.table(rows)
    else:
        st.info("No tasks match this filter.")

    # --- Conflict warnings, shown immediately, before plan generation ---
    conflicts = scheduler.detect_conflicts(all_tasks)
    if conflicts:
        st.warning("⚠️ Scheduling conflicts detected:")
        for warning in conflicts:
            st.write(f"- {warning}")
    else:
        st.success("No time conflicts detected.")

    # --- Mark tasks complete ---
    st.markdown("### Mark a task complete")
    incomplete_tasks = [(p, t) for p, t in all_tasks if not t.completed]
    if incomplete_tasks:
        labels = [f"{p.name}: {t.name}" for p, t in incomplete_tasks]
        choice = st.selectbox("Task", labels)
        chosen_pet, chosen_task = incomplete_tasks[labels.index(choice)]

        if st.button("Mark complete"):
            next_task = chosen_pet.complete_task(chosen_task.id)
            if next_task:
                st.success(
                    f"Marked '{chosen_task.name}' complete. "
                    f"Next occurrence scheduled for {next_task.due_date}."
                )
            else:
                st.success(f"Marked '{chosen_task.name}' complete.")
    else:
        st.caption("No incomplete tasks to mark.")

st.divider()

# --- Build schedule ---
st.subheader("Build Schedule")

if st.button("Generate schedule"):
    scheduler = Scheduler(owner)
    plan, skipped = scheduler.generate_plan()

    if not plan:
        st.warning("No tasks fit in today's schedule. Add some tasks or increase available time.")
    else:
        st.success(f"Today's plan for {owner.name}:")
        rows = [
            {
                "priority": t.priority,
                "pet": p.name,
                "task": t.name,
                "duration_min": t.duration_minutes,
            }
            for p, t in plan
        ]
        st.table(rows)
        total_used = sum(t.duration_minutes for _, t in plan)
        st.caption(f"Total time used: {total_used}/{owner.available_minutes} minutes")

    if skipped:
        st.markdown("**Skipped (not enough time today):**")
        for pet, task in skipped:
            st.write(f"- {pet.name}: {task.name} ({task.duration_minutes} min)")

st.divider()
st.subheader("🤖 Agentic Review")
st.caption(
    "Review the greedy plan against constraints (e.g. meds must never be "
    "skipped) and auto-correct if a violation is found."
)

agent_mode = st.radio(
    "Review mode",
    ["mock (no API key needed)", "live (real Gemini reasoning)"],
    horizontal=True,
)

if st.button("Run Agentic Review"):
    mode = "mock" if agent_mode.startswith("mock") else "live"
    with st.spinner("Agent reviewing plan..."):
        plan, skipped, trace = run_agentic_loop(owner, mode=mode, max_iterations=3)

    for entry in trace:
        review = entry["review"]
        with st.expander(
            f"Iteration {entry['iteration']} — "
            f"{'✅ Approved' if review['approved'] else '⚠️ Revision needed'}",
            expanded=not review["approved"] or entry["iteration"] == len(trace),
        ):
            st.code(entry["plan_summary"], language="text")
            if review["issues"]:
                st.warning("Issues found:")
                for issue in review["issues"]:
                    st.write(f"- {issue}")
            else:
                st.success("No issues found.")
            st.caption(f"Confidence: {review['confidence']}")

    st.markdown("### Final Approved Plan")
    if plan:
        rows = [
            {"pet": p.name, "task": t.name, "priority": t.priority, "duration_min": t.duration_minutes}
            for p, t in plan
        ]
        st.table(rows)
    if skipped:
        st.caption("Still skipped:")
        for p, t in skipped:
            st.write(f"- {p.name}: {t.name}")