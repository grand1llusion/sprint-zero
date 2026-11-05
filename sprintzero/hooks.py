"""Strands hooks and tools used by the cast (workshop modules 1-3, applied).

StayInCharacter is a Strands HookProvider that steers every teammate deterministically: after each
model call it checks the reply against plain-code rules (no "as an AI", no scores or rubrics, no
lists or emojis, short dialogue only). If a reply breaks a rule, the hook sets `retry` so Strands
discards it and asks the model again, at most `max_retries` times per turn. The model never sees the
rules being enforced; code owns them.

define_term is a Strands @tool that lets Sam, the Scrum Master, look up a plain-language Scrum term in
the shared glossary while coaching, so definitions come from vetted wording, not the model's memory.
"""
from __future__ import annotations

import re
from typing import Any

from strands import tool
from strands.hooks import AfterModelCallEvent, BeforeInvocationEvent, HookProvider, HookRegistry

from .packs import load_glossary

BREAKS_CHARACTER = [
    (re.compile(r"\b(as an ai|language model|i am an ai|i'm an ai)\b", re.I), "mentions being an AI"),
    (re.compile(r"\b(rubric|your score|graded|grade of)\b", re.I), "mentions scores or rubrics"),
    (re.compile(r"^\s*([-*•]|\d+\.)\s", re.M), "uses a list"),
    (re.compile(r"[\U0001F300-\U0001FAFF☀-➿]"), "uses emojis"),
]


def check_reply(text: str, max_chars: int) -> list[str]:
    """The plain-code rules a teammate's line must pass. Returns the rules it breaks."""
    problems = [why for pattern, why in BREAKS_CHARACTER if pattern.search(text)]
    if len(text) > max_chars:
        problems.append("too long")
    return problems


def _text(message: dict[str, Any]) -> str:
    return "".join(block.get("text", "") for block in message.get("content", []) if isinstance(block, dict))


class StayInCharacter(HookProvider):
    """Retries a model reply that breaks character. Records every correction in `log`."""

    def __init__(self, max_retries: int = 1, max_chars: int = 600):
        self.max_retries, self.max_chars = max_retries, max_chars
        self.retries_this_turn = 0
        self.log: list[dict[str, Any]] = []

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeInvocationEvent, self._new_turn)
        registry.add_callback(AfterModelCallEvent, self._check)

    def _new_turn(self, event: BeforeInvocationEvent) -> None:
        self.retries_this_turn = 0

    def _check(self, event: AfterModelCallEvent) -> None:
        response = event.stop_response
        if response is None or response.stop_reason == "tool_use":
            return  # errors are Strands' to handle; tool calls are not dialogue yet
        problems = check_reply(_text(response.message), self.max_chars)
        if problems and self.retries_this_turn < self.max_retries:
            self.retries_this_turn += 1
            self.log.append({"agent": getattr(event.agent, "name", None), "problems": problems})
            event.retry = True


@tool
def define_term(term: str) -> str:
    """Look up a Scrum term in Sprint Zero's plain-language glossary.

    Args:
        term: The Scrum term to define, for example "Sprint Goal" or "Definition of Done".
    """
    glossary = load_glossary()
    wanted = re.sub(r"[^a-z]", "", term.lower())
    for key, entry in glossary.items():
        if wanted in (re.sub(r"[^a-z]", "", key.lower()), re.sub(r"[^a-z]", "", entry["name"].lower())):
            return f"{entry['name']}: {' '.join(entry['meaning'].split())}"
    return f"'{term}' is not in the glossary. Known terms: " + ", ".join(e["name"] for e in glossary.values())
