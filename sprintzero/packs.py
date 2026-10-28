"""Scenario packs are data. This module loads them and checks them, so a broken pack fails early."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PACKS_DIR = Path(__file__).resolve().parent.parent / "packs"
LEVELS = ("strong", "partial", "weak", "off_topic")


class PackError(ValueError):
    """A scenario pack or the team file is missing something the engine needs."""


def _read(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_team(path: Path | None = None) -> dict[str, Any]:
    team = _read(path or PACKS_DIR / "team.yaml")
    if not team.get("scrum_master") or not team.get("developers"):
        raise PackError("team.yaml needs a scrum_master and developers")
    return team


def _check_rubric(where: str, rubric: Any, problems: list[str]) -> None:
    if not isinstance(rubric, dict) or set(rubric) != set(LEVELS):
        problems.append(f"{where}: rubric needs exactly {', '.join(LEVELS)}")


def load_pack(pack: str | Path, team: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load a pack by id (a folder under packs/) or by path to its pack.yaml, and validate it."""
    path = Path(pack)
    if not path.suffix:
        path = PACKS_DIR / str(pack) / "pack.yaml"
    data = _read(path)
    team = team or load_team()
    problems: list[str] = []
    for key in ("id", "title", "product", "stakeholders", "backlog", "planning", "briefing",
                "sprint_goal", "injects", "quiz", "capacity_points", "sprint_days"):
        if key not in data:
            problems.append(f"missing '{key}'")
    if problems:
        raise PackError(f"{path}: " + "; ".join(problems))

    people = {s["id"] for s in data["stakeholders"]} | {d["id"] for d in team["developers"]}
    people.add(team["scrum_master"]["id"])
    developers = {d["id"] for d in team["developers"]}
    items = {b["id"] for b in data["backlog"]}

    _check_rubric("briefing", data["briefing"].get("rubric"), problems)
    _check_rubric("sprint_goal", data["sprint_goal"].get("rubric"), problems)
    if data["briefing"].get("from") not in people:
        problems.append("briefing: 'from' is not a known person")
    for group in ("must_include", "should_include", "should_exclude"):
        unknown = set(data["planning"].get(group, [])) - items
        if unknown:
            problems.append(f"planning.{group}: unknown items {sorted(unknown)}")
    seen = set()
    for inj in data["injects"]:
        where = f"inject {inj.get('id')}"
        if inj.get("id") in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(inj.get("id"))
        if inj.get("from") not in people:
            problems.append(f"{where}: 'from' is not a known person")
        if not set(inj.get("react", [])) <= developers:
            problems.append(f"{where}: 'react' must list developer ids")
        if not 1 <= int(inj.get("day", 0)) <= int(data["sprint_days"]):
            problems.append(f"{where}: day outside the Sprint")
        for key in ("text", "prompt", "competency", "coach_point", "ideal"):
            if not inj.get(key):
                problems.append(f"{where}: missing '{key}'")
        _check_rubric(where, inj.get("rubric"), problems)
    for i, q in enumerate(data["quiz"]):
        if not 0 <= int(q.get("answer", -1)) < len(q.get("options", [])):
            problems.append(f"quiz {i + 1}: answer index out of range")
    if problems:
        raise PackError(f"{path}: " + "; ".join(problems))
    data["injects"] = sorted(data["injects"], key=lambda i: int(i["day"]))
    return data


def person(pack: dict[str, Any], team: dict[str, Any], person_id: str) -> dict[str, Any]:
    """Look up anyone in the scenario: a developer, the Scrum Master or a stakeholder."""
    for p in team["developers"] + [team["scrum_master"]] + pack["stakeholders"]:
        if p["id"] == person_id:
            return p
    raise KeyError(person_id)
