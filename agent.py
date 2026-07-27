"""
ScheduleAgent: an agentic reviewer for PawPal+ schedules.

Scheduler.generate_plan() produces a plan using a fixed greedy rule
(priority, then duration). That rule is fast and predictable but has no
sense of which constraints actually matter to a pet owner, e.g. "never skip
a meds task." ScheduleAgent closes that gap: it reviews a generated plan
against a small set of stated constraints, and if it finds a violation, it
tells the Scheduler which specific task to force-include and why. The loop
in run_agentic_loop() repeats this until the plan passes review or a
maximum number of iterations is reached, so the agent can never spin forever
or silently fail.

Two modes are supported:
- "mock": a deterministic, rule-based stand-in for the LLM. No API key or
  network needed. Used for automated tests and the reliability harness so
  results are reproducible.
- "live": calls the Gemini API (gemini-2.5-flash, free tier) to actually
  reason about the plan in natural language and return a structured verdict.
"""

import json
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from pawpal_system import Owner, Pet, Task, Scheduler


# Constraints the agent checks the plan against. Kept as plain strings so
# they can be shown to a human, embedded in a prompt, or checked by simple
# rules in mock mode.
CONSTRAINTS = [
    "A task in the 'meds' category must never be skipped.",
    "No pet should be left with zero scheduled tasks today if it has at "
    "least one incomplete task.",
    "No more than one task per pet should be skipped, if avoidable within "
    "the available time budget.",
]


@dataclass
class ReviewResult:
    approved: bool
    issues: List[str]
    force_include_ids: List[str]
    confidence: float
    raw_reasoning: str

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "issues": self.issues,
            "force_include_ids": self.force_include_ids,
            "confidence": self.confidence,
            "raw_reasoning": self.raw_reasoning,
        }


def _summarize_plan(plan: List[Tuple[Pet, Task]], skipped: List[Tuple[Pet, Task]]) -> str:
    """Builds a compact plain-text summary of a plan for the agent to review,
    whether that reviewer is an LLM prompt or a human reading a log."""
    lines = ["SCHEDULED:"]
    for pet, task in plan:
        lines.append(
            f"  - id={task.id} pet={pet.name} task={task.name} "
            f"category={task.category} priority={task.priority} "
            f"duration={task.duration_minutes}min"
        )
    lines.append("SKIPPED:")
    for pet, task in skipped:
        lines.append(
            f"  - id={task.id} pet={pet.name} task={task.name} "
            f"category={task.category} priority={task.priority} "
            f"duration={task.duration_minutes}min"
        )
    return "\n".join(lines)


class ScheduleAgent:
    def __init__(self, mode: str = "mock", model: str = "gemini-3.5-flash"):
        """Builds a schedule-reviewing agent. mode='mock' uses deterministic
        rules and needs no API key. mode='live' calls the Gemini API and
        requires a GEMINI_API_KEY environment variable."""
        if mode not in ("mock", "live"):
            raise ValueError("mode must be 'mock' or 'live'")
        self.mode = mode
        self.model = model
        self._client = None

        if self.mode == "live":
            # Imported lazily so mock mode never requires the dependency
            # or an API key to be present.
            from google import genai
            self._client = genai.Client()

    def review_plan(
        self, plan: List[Tuple[Pet, Task]], skipped: List[Tuple[Pet, Task]]
    ) -> ReviewResult:
        """Reviews a plan against CONSTRAINTS and returns a ReviewResult."""
        if self.mode == "mock":
            return self._review_mock(plan, skipped)
        return self._review_live(plan, skipped)

    # --- Mock mode: deterministic, no API needed ---

    def _review_mock(
        self, plan: List[Tuple[Pet, Task]], skipped: List[Tuple[Pet, Task]]
    ) -> ReviewResult:
        issues = []
        force_ids = []

        skipped_meds = [(p, t) for p, t in skipped if t.category == "meds"]
        for pet, task in skipped_meds:
            issues.append(f"Meds task '{task.name}' for {pet.name} was skipped.")
            force_ids.append(task.id)

        scheduled_pet_names = {pet.name for pet, _ in plan}
        all_pet_names = {pet.name for pet, _ in plan + skipped}
        zeroed_pets = all_pet_names - scheduled_pet_names
        for pet_name in zeroed_pets:
            pet_skipped = [(p, t) for p, t in skipped if p.name == pet_name]
            if pet_skipped:
                # Force-include the pet's highest priority skipped task so
                # they get at least one thing scheduled today.
                pet_skipped.sort(key=lambda pt: (pt[1].priority != "high", pt[1].duration_minutes))
                pet, task = pet_skipped[0]
                issues.append(f"{pet.name} has zero scheduled tasks today.")
                force_ids.append(task.id)

        approved = len(issues) == 0
        confidence = 1.0 if approved else max(0.4, 1.0 - 0.2 * len(issues))

        return ReviewResult(
            approved=approved,
            issues=issues,
            force_include_ids=list(set(force_ids)),
            confidence=round(confidence, 2),
            raw_reasoning="(mock mode: rule-based check, no LLM call made)",
        )

    # --- Live mode: calls Gemini ---

    def _review_live(
        self, plan: List[Tuple[Pet, Task]], skipped: List[Tuple[Pet, Task]]
    ) -> ReviewResult:
        summary = _summarize_plan(plan, skipped)
        constraints_text = "\n".join(f"- {c}" for c in CONSTRAINTS)

        prompt = f"""You are reviewing a pet care schedule generated by a
greedy priority-based algorithm. Check it against these constraints:

{constraints_text}

Here is today's plan:

{summary}

Respond with ONLY a JSON object, no markdown fences, no extra text, in
exactly this shape:
{{
  "approved": true or false,
  "issues": ["short description of each violation, empty list if none"],
  "force_include_ids": ["task id strings that must be scheduled to fix the violations"],
  "confidence": a number between 0 and 1 for how sure you are in this review
}}
"""

        try:
            response = self._client.models.generate_content(
                model=self.model, contents=prompt
            )
            raw_text = response.text.strip()
            # Guardrail: strip accidental markdown fences before parsing,
            # since models sometimes wrap JSON in ```json anyway.
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`")
                raw_text = raw_text.replace("json", "", 1).strip()

            parsed = json.loads(raw_text)
            return ReviewResult(
                approved=bool(parsed.get("approved", False)),
                issues=list(parsed.get("issues", [])),
                force_include_ids=list(parsed.get("force_include_ids", [])),
                confidence=float(parsed.get("confidence", 0.5)),
                raw_reasoning=raw_text,
            )
        except Exception as e:
            # Guardrail: never let an API failure or a malformed response
            # crash the scheduling flow. Fall back to "approved" so the
            # owner still gets a usable plan, but flag it clearly as a
            # fallback rather than a real review.
            return ReviewResult(
                approved=True,
                issues=[],
                force_include_ids=[],
                confidence=0.0,
                raw_reasoning=f"(agent error, fell back to unreviewed plan: {e})",
            )


def run_agentic_loop(
    owner: Owner, mode: str = "mock", max_iterations: int = 3, log_path: Optional[str] = None
) -> Tuple[List[Tuple[Pet, Task]], List[Tuple[Pet, Task]], List[dict]]:
    """Runs the plan -> review -> correct loop up to max_iterations times.
    Returns (final_plan, final_skipped, trace), where trace is a list of
    per-iteration dicts suitable for logging to ai_interactions.md."""
    scheduler = Scheduler(owner)
    agent = ScheduleAgent(mode=mode)

    force_ids: List[str] = []
    trace = []

    for iteration in range(1, max_iterations + 1):
        plan, skipped = scheduler.generate_plan(force_include_ids=force_ids)
        review = agent.review_plan(plan, skipped)

        trace.append({
            "iteration": iteration,
            "plan_summary": _summarize_plan(plan, skipped),
            "review": review.to_dict(),
        })

        if review.approved:
            break

        # Adopt the agent's suggested corrections for the next iteration.
        force_ids = list(set(force_ids) | set(review.force_include_ids))

    if log_path:
        with open(log_path, "a") as f:
            f.write(f"\n## Agentic run — {len(trace)} iteration(s)\n")
            for entry in trace:
                f.write(f"\n**Iteration {entry['iteration']}**\n")
                f.write(f"```\n{entry['plan_summary']}\n```\n")
                f.write(f"Review: {json.dumps(entry['review'], indent=2)}\n")

    return plan, skipped, trace