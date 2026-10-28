"""The cast, played by Strands agents on Amazon Bedrock.

Each developer, the Scrum Master and each stakeholder is its own Strands Agent with its own persona
and memory of the session. The sprint engine decides WHO speaks for each event (one to three people,
never all nine), so sessions stay fast and cheap enough to serve many learners. Agents never score
anything: they react in character, and the Scrum Master coaches.
"""
from __future__ import annotations

import os
import re
from typing import Any, Callable

from .grading import Grade
from .packs import person

MODEL_ID = os.environ.get("SPRINTZERO_MODEL", "us.amazon.nova-lite-v1:0")
COACH_MODEL_ID = os.environ.get("SPRINTZERO_COACH_MODEL", MODEL_ID)
THINKING = re.compile(r"<thinking>.*?(</thinking>|$)", re.S)

# How the Product Owner's call lands on the person reacting. Personas react to consequences, not scores.
MOOD = {
    "strong": "The Product Owner's call makes your work clearer or easier. React naturally; you may be relieved or supportive.",
    "partial": "The Product Owner's call helps a little but leaves something unresolved for you. Say what is still unclear.",
    "weak": "The Product Owner's call creates a real problem for you. Push back respectfully, in character, and say what it will cost.",
    "off_topic": "The Product Owner did not really answer. Ask, in character, for a clear answer.",
}


def make_model(model_id: str | None = None, temperature: float = 0.7):
    from strands.models import BedrockModel
    return BedrockModel(model_id=model_id or MODEL_ID, region_name=os.environ.get("AWS_REGION", "us-east-1"),
                        temperature=temperature, max_tokens=300)


def make_agent(system_prompt: str, model=None, name: str | None = None):
    from strands import Agent
    from strands.agent.conversation_manager import SlidingWindowConversationManager
    return Agent(model=model or make_model(), system_prompt=system_prompt, name=name, callback_handler=None,
                 conversation_manager=SlidingWindowConversationManager(window_size=8))


def clean(text: str) -> str:
    return THINKING.sub("", str(text)).strip().strip('"').strip()


class Cast:
    """Holds one Strands agent per person, created on first use."""

    def __init__(self, pack: dict[str, Any], team: dict[str, Any],
                 agent_factory: Callable[[str, str], Any] | None = None):
        self.pack, self.team = pack, team
        self.agent_factory = agent_factory or (lambda prompt, name: make_agent(prompt, name=name))
        self._agents: dict[str, Any] = {}

    def _persona_prompt(self, p: dict[str, Any]) -> str:
        product = self.pack["product"]
        note = self.pack.get("team_notes", {}).get(p["id"], "")
        return (
            f"You are {p['name']}, {p['role']}, in a workplace simulation that teaches Scrum to people "
            f"starting their careers. The learner plays the Product Owner of {product['name']}.\n"
            f"Product: {' '.join(product['summary'].split())}\n"
            f"Your persona: {' '.join(p['persona'].split())}\n"
            + (f"This week: {note}\n" if note else "")
            + "Rules: speak as yourself in one or two short sentences of natural dialogue. No stage "
              "directions, no lists, no emojis. Stay kind and workplace-appropriate. Never mention scores, "
              "rubrics or that you are an AI. Never decide things that belong to the Product Owner."
        )

    def agent(self, person_id: str):
        if person_id not in self._agents:
            p = person(self.pack, self.team, person_id)
            self._agents[person_id] = self.agent_factory(self._persona_prompt(p), p["name"])
        return self._agents[person_id]

    def react(self, speakers: list[str], situation: str, po_answer: str, grade: Grade) -> list[dict[str, str]]:
        """One short line from each speaker, in order; each hears the lines before theirs."""
        lines: list[dict[str, str]] = []
        for pid in speakers:
            p = person(self.pack, self.team, pid)
            said = "\n".join(f"{line['name']}: {line['text']}" for line in lines) or "(nobody yet)"
            prompt = (f"Situation: {' '.join(situation.split())}\n"
                      f"The Product Owner said: \"{po_answer.strip()[:1200]}\"\n"
                      f"Teammates who already spoke:\n{said}\n\n{MOOD[grade.level]}\nYour line:")
            lines.append({"id": pid, "name": p["name"], "role": p["role"], "text": clean(self.agent(pid)(prompt))})
        return lines

    def coach(self, situation: str, po_answer: str, grade: Grade, coach_point: str, ideal: str) -> str:
        """Sam, the Scrum Master, gives a short coaching note. Sam never states a score."""
        sm = self.team["scrum_master"]["id"]
        prompt = (f"Coach the Product Owner privately in two or three sentences. Start with what they did "
                  f"well (if anything), then one specific improvement, then the principle in plain words.\n"
                  f"Situation: {' '.join(situation.split())}\n"
                  f"The Product Owner said: \"{po_answer.strip()[:1200]}\"\n"
                  f"How it landed: {grade.level.replace('_', ' ')}.\n"
                  f"Principle to teach: {' '.join(coach_point.split())}\n"
                  f"An example of a strong answer, for your reference only: {' '.join(ideal.split())}")
        return clean(self.agent(sm)(prompt))
