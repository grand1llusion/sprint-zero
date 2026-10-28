"""The sprint engine owns the clock, the state and the order of events. Agents only react to it.

A session is a list of steps built from the scenario pack:
  quiz_pre -> briefing (Product Goal) -> planning -> sprint_goal -> injects by day -> quiz_post -> debrief

`current()` describes the step the learner is on; `submit(answer)` grades it, logs the decision,
asks the right people to react, and moves on. All state is plain JSON (`state`), so a web server
can keep sessions in a database and stay stateless.
"""
from __future__ import annotations

import copy
from typing import Any

from .grading import Grade
from .packs import load_glossary, person
from .scoring import COMPETENCY_NAMES, planning_points, quiz_points, score

MAX_SPEAKERS = 3
GLOSSARY = load_glossary()

# How to read a backlog card, shown during Sprint Planning.
BACKLOG_LEGEND = [
    {"part": "B1", "label": "Item ID", "meaning": "A short label so everyone can talk about the same item."},
    {"part": "Residents sign up by texting RIVER…", "label": "Backlog item",
     "meaning": "Something the people using the product need. You decide which ones come first."},
    {"part": "high value", "label": "Value",
     "meaning": "How much it matters to residents and the sponsor: high, medium, low, or unclear."},
    {"part": "5 pts", "label": "Size (story points)",
     "meaning": "The team's estimate of effort, relative rather than hours. '??' means it can't be sized yet."},
]


def terms_for(keys: list[str]) -> list[dict[str, str]]:
    return [{"term": GLOSSARY[k]["name"], "meaning": " ".join(GLOSSARY[k]["meaning"].split())} for k in keys]


class SessionError(ValueError):
    """The learner's answer cannot be used for this step (for example an unknown backlog item)."""


class Session:
    def __init__(self, pack: dict[str, Any], team: dict[str, Any], grader, cast,
                 state: dict[str, Any] | None = None):
        self.pack, self.team, self.grader, self.cast = pack, team, grader, cast
        self.state = copy.deepcopy(state) if state else {"pack": pack["id"], "version": pack.get("version", 1),
                                                          "step": 0, "log": [], "selected": []}
        self.steps = ([("quiz", "quiz_pre"), ("text", "briefing"), ("planning", "planning"),
                       ("text", "sprint_goal")]
                      + [("text", inj["id"]) for inj in pack["injects"]]
                      + [("quiz", "quiz_post"), ("debrief", "debrief")])

    # ------------------------------------------------------------------ describing the current step
    @property
    def finished(self) -> bool:
        return self.steps[self.state["step"]][0] == "debrief"

    def _who(self, person_id: str) -> dict[str, str]:
        p = person(self.pack, self.team, person_id)
        return {"id": p["id"], "name": p["name"], "role": p["role"]}

    def _text_step(self, step_id: str) -> dict[str, Any]:
        """The pack data behind a free-text step: briefing, sprint_goal or an inject."""
        if step_id == "briefing":
            b = self.pack["briefing"]
            return {**b, "id": "briefing", "day": 0, "title": "The briefing",
                    "prompt": "What is the Product Goal you want this team working toward?",
                    "react": b.get("react", [b["from"], "leah"])}
        if step_id == "sprint_goal":
            g = self.pack["sprint_goal"]
            return {**g, "id": "sprint_goal", "day": 0, "title": "The Sprint Goal",
                    "from": self.team["scrum_master"]["id"], "text": g["prompt"],
                    "react": g.get("react", ["priya"])}
        return next(i for i in self.pack["injects"] if i["id"] == step_id)

    def current(self) -> dict[str, Any]:
        kind, step_id = self.steps[self.state["step"]]
        base = {"kind": kind, "step": step_id, "number": self.state["step"] + 1, "of": len(self.steps)}
        if kind == "quiz":
            pre = step_id == "quiz_pre"
            title = "Optional warm-up: 5 quick questions" if pre else "Optional: the same 5 questions again"
            note = ("No pressure: guess if you're not sure. This measures how much the simulator teaches, "
                    "not you. You can skip it." if pre else
                    "See how much has changed since you started. You can skip it.")
            return {**base, "title": title, "note": note, "optional": True,
                    "questions": [{"q": q["q"], "options": q["options"]} for q in self.pack["quiz"]]}
        if kind == "planning":
            return {**base, "title": "Sprint Planning", "day": 1,
                    "capacity": self.pack["capacity_points"],
                    "backlog": [{k: b.get(k) for k in ("id", "title", "value", "points")} for b in self.pack["backlog"]],
                    "prompt": (f"Choose the backlog items for this {self.pack['sprint_days']}-day Sprint, in priority "
                               f"order. The team can take about {self.pack['capacity_points']} points."),
                    "legend": BACKLOG_LEGEND,
                    "terms": terms_for(self.pack["planning"].get("terms", []) + ["value", "story_points"])}
        if kind == "debrief":
            return {**base, "title": "Debrief", "result": self.result()}
        s = self._text_step(step_id)
        return {**base, "title": s["title"], "day": s["day"], "speaker": self._who(s["from"]),
                "text": " ".join(s["text"].split()), "prompt": s["prompt"],
                "help": " ".join(s.get("help", "").split()),
                "terms": terms_for(s.get("terms", [])),
                "reacting": [self._who(pid)["name"] for pid in self._speakers(s)]}

    # ------------------------------------------------------------------ handling an answer
    def submit(self, answer: Any, help_used: bool = False) -> dict[str, Any]:
        """Answer the current step. `help_used` records that the learner started from the HELP example."""
        if self.finished:
            raise SessionError("the session is over")
        kind, step_id = self.steps[self.state["step"]]
        if kind == "text":
            result = self._submit_text(step_id, answer, bool(help_used))
        else:
            result = {"quiz": self._submit_quiz, "planning": self._submit_planning}[kind](step_id, answer)
        self.state["step"] += 1
        result["next"] = self.current()
        return result

    def _submit_quiz(self, step_id: str, answer: Any) -> dict[str, Any]:
        n = len(self.pack["quiz"])
        if answer is None or answer == "skip":
            self.state["log"].append({"kind": "quiz", "step": step_id, "skipped": True})
            return {"skipped": True, "of": n}
        if not isinstance(answer, list) or len(answer) != n or not all(isinstance(a, int) for a in answer):
            raise SessionError(f"answer all {n} questions with option numbers")
        self.state["log"].append({"kind": "quiz", "step": step_id, "answer": answer})
        return {"correct": quiz_points(self.pack, answer), "of": n}

    def _context(self, s: dict[str, Any]) -> str:
        goal = next((e["answer"] for e in self.state["log"] if e["step"] == "briefing"), "")
        sprint = next((e["answer"] for e in self.state["log"] if e["step"] == "sprint_goal"), "")
        speaker = person(self.pack, self.team, s["from"])
        return (f"PRODUCT: {' '.join(self.pack['product']['summary'].split())}\n"
                + (f"PRODUCT GOAL: {goal}\n" if goal else "")
                + (f"SPRINT GOAL: {sprint}\nSPRINT ITEMS: {', '.join(self.state['selected'])}\n" if sprint else "")
                + f"SITUATION (day {s['day']}): {speaker['name']} ({speaker['role']}) says: {' '.join(s['text'].split())}")

    def _speakers(self, s: dict[str, Any]) -> list[str]:
        """Who reacts to a free-text step: a stakeholder who raised it, then the people it affects."""
        raised_by = [s["from"]] if s["from"] not in self._developers() and s["from"] != self.team["scrum_master"]["id"] else []
        return list(dict.fromkeys(raised_by + s["react"]))[:MAX_SPEAKERS]

    def _submit_text(self, step_id: str, answer: Any, help_used: bool = False) -> dict[str, Any]:
        answer = str(answer or "").strip()
        s = self._text_step(step_id)
        grade: Grade = self.grader.grade(s["prompt"], s["rubric"], answer, self._context(s))
        self.state["log"].append({"kind": "text", "step": step_id, "competency": s["competency"],
                                  "answer": answer, "grade": grade.to_dict(), "help_used": help_used})
        situation = f"Day {s['day']}. {self._who(s['from'])['name']} said: {s['text']}"
        reactions = self.cast.react(self._speakers(s), situation, answer, grade)
        coach = self.cast.coach(situation, answer, grade, s.get("coach_point", s["rubric"]["strong"]),
                                s.get("ideal", ""))
        return {"grade": grade.to_dict(), "competency": COMPETENCY_NAMES.get(s["competency"], s["competency"]),
                "reactions": reactions, "coach": coach, "ideal": " ".join(s.get("ideal", "").split())}

    def _submit_planning(self, step_id: str, answer: Any) -> dict[str, Any]:
        items = {b["id"] for b in self.pack["backlog"]}
        chosen = [str(a).strip().upper() for a in (answer or [])]
        unknown = [a for a in chosen if a not in items]
        if not chosen or unknown:
            raise SessionError(f"choose items by id ({', '.join(sorted(items))})"
                               + (f"; unknown: {', '.join(unknown)}" if unknown else ""))
        chosen = list(dict.fromkeys(chosen))
        self.state["selected"] = chosen
        self.state["log"].append({"kind": "planning", "step": step_id, "answer": chosen})
        result = planning_points(self.pack, chosen)
        titles = {b["id"]: b["title"] for b in self.pack["backlog"]}
        said = "I'd like the Sprint to take: " + "; ".join(f"{i} {titles[i]}" for i in chosen)
        grade = Grade(result["level"], None, "planning-rules")
        situation = (f"Day 1, Sprint Planning. Capacity is about {self.pack['capacity_points']} points. "
                     f"{'; '.join(result['notes'])}.")
        speakers = ["kenji"] if any(self._item(i).get("vague") for i in chosen) else []
        reactions = self.cast.react(list(dict.fromkeys(speakers + ["priya", "marcus"]))[:MAX_SPEAKERS],
                                    situation, said, grade)
        coach = self.cast.coach(situation, said, grade, self.pack["planning"]["explain"], "")
        return {"grade": grade.to_dict(), "competency": COMPETENCY_NAMES["backlog_ordering"],
                "planning": result, "reactions": reactions, "coach": coach}

    # ------------------------------------------------------------------ helpers
    def _developers(self) -> set[str]:
        return {d["id"] for d in self.team["developers"]}

    def _item(self, item_id: str) -> dict[str, Any]:
        return next(b for b in self.pack["backlog"] if b["id"] == item_id)

    def result(self) -> dict[str, Any]:
        r = score(self.pack, self.state["log"])
        r["competency_names"] = {k: COMPETENCY_NAMES.get(k, k) for k in r["competencies"]}
        return r
