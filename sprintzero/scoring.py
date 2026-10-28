"""Scoring is plain, deterministic code over the decision log, so any run can be re-scored on a
server and a score typed into a browser never counts. No model computes a score."""
from __future__ import annotations

from typing import Any

POINTS = {"strong": 30, "partial": 10, "weak": -20, "off_topic": -10}
COMPETENCY_NAMES = {
    "product_goal": "Setting a Product Goal",
    "backlog_ordering": "Choosing the Sprint's work",
    "sprint_goal": "Writing a Sprint Goal",
    "scope_change": "Handling scope creep",
    "acceptance_criteria": "Making work testable",
    "team_autonomy": "Trusting the team",
    "adapting_plan": "Adapting to change",
    "definition_of_done": "Holding the Definition of Done",
}
MEDALS = ((0.85, "Gold"), (0.70, "Silver"), (0.50, "Bronze"))


def planning_points(pack: dict[str, Any], selected: list[str]) -> dict[str, Any]:
    """Score the learner's Sprint selection against the pack's planning rules."""
    plan = pack["planning"]
    sizes = {b["id"]: b.get("points") for b in pack["backlog"]}
    chosen = set(selected)
    total = sum(sizes[i] or 0 for i in chosen)
    notes, points = [], 0
    if any(sizes[i] is None for i in chosen):
        points -= 10
        notes.append("an item with no size or acceptance criteria was pulled into the Sprint")
    if total <= pack["capacity_points"]:
        points += 20
        notes.append(f"{total} of {pack['capacity_points']} points: within capacity")
    else:
        points -= 20
        notes.append(f"{total} points is over the team's capacity of {pack['capacity_points']}")
    missing = [i for i in plan.get("must_include", []) if i not in chosen]
    points += 10 * (len(plan.get("must_include", [])) - len(missing)) - 15 * len(missing)
    if missing:
        notes.append("missing essentials: " + ", ".join(missing))
    points += 5 * len(chosen & set(plan.get("should_include", [])))
    extra = sorted(chosen & set(plan.get("should_exclude", [])))
    points -= 10 * len(extra)
    if extra:
        notes.append("better left for later: " + ", ".join(extra))
    best = 20 + 10 * len(plan.get("must_include", [])) + 5 * len(plan.get("should_include", []))
    level = "strong" if points >= best - 5 else "partial" if points > 0 else "weak"
    return {"points": points, "max": best, "level": level, "total_size": total, "notes": notes}


def quiz_points(pack: dict[str, Any], answers: list[int]) -> int:
    return sum(1 for q, a in zip(pack["quiz"], answers) if a == q["answer"])


def score(pack: dict[str, Any], log: list[dict[str, Any]]) -> dict[str, Any]:
    """Re-score a whole run from its decision log."""
    total, best_total, competencies, flags, quiz, helps = 0, 0, {}, [], {}, 0
    for entry in log:
        kind = entry["kind"]
        if kind == "quiz":
            if not entry.get("skipped"):
                quiz[entry["step"]] = quiz_points(pack, entry["answer"])
            continue
        if kind == "planning":
            result = planning_points(pack, entry["answer"])
            total += result["points"]
            best_total += result["max"]
            competencies["backlog_ordering"] = result["level"]
            continue
        helps += 1 if entry.get("help_used") else 0
        level = entry["grade"]["level"]
        total += POINTS[level]
        best_total += POINTS["strong"]
        competencies[entry["competency"]] = level
        if entry["grade"].get("low_confidence"):
            flags.append(f"{entry['step']}: low-confidence grade, worth a human look")
    ratio = total / best_total if best_total else 0.0
    medal = next((name for cut, name in MEDALS if ratio >= cut), None)
    return {"score": total, "max": best_total, "percent": round(100 * max(ratio, 0)),
            "medal": medal, "competencies": competencies, "quiz": quiz, "flags": flags, "help_used": helps}
