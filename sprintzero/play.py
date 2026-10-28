"""Play one Sprint in a terminal:  python -m sprintzero.play [--pack flood-alert]

Needs AWS credentials with Amazon Bedrock access (for example AWS CloudShell). Set
STRANDS_DECIDER_URL to grade with a Strands Decider 2B server; otherwise a Bedrock model grades.
"""
from __future__ import annotations

import argparse
import json
import os
import textwrap
import time

from .agents import Cast, make_agent, make_model
from .engine import Session, SessionError
from .grading import BedrockGrader, DeciderGrader, FallbackGrader
from .packs import load_pack, load_team

BOLD, DIM, CYAN, GREEN, YELLOW, RED, RESET = "\033[1m", "\033[2m", "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"
LEVEL_COLOUR = {"strong": GREEN, "partial": YELLOW, "weak": RED, "off_topic": RED}


def say(text: str = "", colour: str = "", indent: int = 0) -> None:
    for para in str(text).split("\n"):
        print(colour + textwrap.fill(para, 88, initial_indent=" " * indent, subsequent_indent=" " * indent) + RESET)


def make_grader():
    bedrock = BedrockGrader(lambda prompt: make_agent(prompt, model=make_model(
        os.environ.get("SPRINTZERO_GRADER_MODEL"), temperature=0.0)))
    if os.environ.get("STRANDS_DECIDER_URL"):
        return FallbackGrader(DeciderGrader(), bedrock)
    return bedrock


def ask_text(prompt: str) -> str:
    say(prompt, BOLD)
    while True:
        answer = input("> ").strip()
        if answer:
            return answer


def play_quiz(step: dict) -> list[int] | None:
    say(step["title"], BOLD + CYAN)
    say(step["note"], DIM)
    if input("Take it? [Y/n] > ").strip().lower().startswith("n"):
        return None
    answers = []
    for n, q in enumerate(step["questions"], 1):
        say(f"\n{n}. {q['q']}")
        for i, option in enumerate(q["options"], 1):
            say(f"{i}) {option}", indent=3)
        while True:
            pick = input("> ").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(q["options"]):
                answers.append(int(pick) - 1)
                break
            say(f"Type a number from 1 to {len(q['options'])}.", DIM)
    return answers


def play_planning(step: dict) -> list[str]:
    say(f"\nDay {step['day']} · {step['title']}", BOLD + CYAN)
    for b in step["backlog"]:
        size = f"{b['points']} pts" if b["points"] is not None else "?? pts"
        say(f"{b['id']}  {b['title']}  {DIM}[{b['value']} value, {size}]{RESET}", indent=2)
    say("")
    answer = ask_text(step["prompt"] + " Type the ids, e.g. B1 B2 B6")
    return answer.replace(",", " ").split()


def show_result(result: dict) -> None:
    if result.get("skipped"):
        say("Skipped.", DIM)
        return
    if "correct" in result:
        say(f"You got {result['correct']} of {result['of']}.", DIM)
        return
    g = result["grade"]
    print()
    for line in result["reactions"]:
        say(f"{line['name']} ({line['role']}): {line['text']}", indent=2)
    print()
    say(f"Sam (Scrum Master, coaching): {result['coach']}", CYAN, indent=2)
    tag = g["level"].replace("_", " ").upper()
    extra = f", confidence {g['confidence']:.0%}" if g.get("confidence") is not None else ""
    say(f"{result['competency']}: {tag}{extra}", LEVEL_COLOUR[g["level"]] + BOLD, indent=2)
    if g["level"] != "strong" and result.get("ideal"):
        say(f"One strong answer: {result['ideal']}", DIM, indent=2)


def show_debrief(r: dict) -> None:
    say("\nDEBRIEF", BOLD + CYAN)
    say(f"Score {r['score']} of {r['max']} ({r['percent']}%)" + (f" · {r['medal']} medal" if r["medal"] else ""), BOLD)
    for key, level in r["competencies"].items():
        say(f"{r['competency_names'][key]}: {level.replace('_', ' ')}", LEVEL_COLOUR[level], indent=2)
    if "quiz_pre" in r["quiz"] and "quiz_post" in r["quiz"]:
        say(f"Quick check: {r['quiz']['quiz_pre']} before, {r['quiz']['quiz_post']} after.", BOLD)
    for flag in r["flags"]:
        say(f"Note: {flag}", DIM)


def main() -> None:
    parser = argparse.ArgumentParser(description="Play one Sprint as the Product Owner.")
    parser.add_argument("--pack", default="flood-alert")
    parser.add_argument("--log", default="sprint-zero-run.json", help="where to save your decision log")
    args = parser.parse_args()
    team = load_team()
    pack = load_pack(args.pack, team)
    session = Session(pack, team, make_grader(), Cast(pack, team))
    say(f"\nSPRINT ZERO · {pack['title']}: {pack['tagline']}", BOLD + CYAN)
    say(" ".join(pack["product"]["summary"].split()))
    say("You are the Product Owner. Sam Whitfield is your Scrum Master; seven developers are your team.", DIM)
    while not session.finished:
        step, help_used = session.current(), False
        if step["kind"] == "quiz":
            answer = play_quiz(step)
        elif step["kind"] == "planning":
            answer = play_planning(step)
        else:
            day = f"Day {step['day']} · " if step["day"] else ""
            say(f"\n{day}{step['title']}", BOLD + CYAN)
            say(f"{step['speaker']['name']} ({step['speaker']['role']}): {step['text']}")
            if step.get("help"):
                say("Need an idea? Type help for an example you can adapt.", DIM)
            answer = ask_text(step["prompt"])
            if answer.lower() == "help" and step.get("help"):
                say(f"Example to adapt (replace each [bracket]): {step['help']}", YELLOW)
                answer, help_used = ask_text(step["prompt"]), True
        try:
            started = time.time()
            say("…", DIM)
            result = session.submit(answer, help_used=help_used)
            show_result(result)
            say(f"({time.time() - started:.1f}s)", DIM)
        except SessionError as exc:
            say(str(exc), RED)
    show_debrief(session.result())
    with open(args.log, "w", encoding="utf-8") as f:
        json.dump(session.state, f, indent=2)
    say(f"\nYour decision log is saved in {args.log}.", DIM)


if __name__ == "__main__":
    main()
