"""Sprint Zero web app: a JSON API around the sprint engine, plus the browser front end.

  GET  /                          the app
  GET  /api/packs                 scenario packs on offer
  POST /api/sessions              start a session  {"pack": "flood-alert"}
  GET  /api/sessions/{id}         the session view (current step, team feed, board)
  POST /api/sessions/{id}/answer  answer the current step  {"step": 3, "answer": ...}

Run locally:  uvicorn sprintzero.web.server:app --port 8080
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..agents import Cast, make_agent, make_model
from ..engine import Session, SessionError
from ..grading import BedrockGrader, DeciderGrader, FallbackGrader
from ..packs import PACKS_DIR, load_pack, load_team, person
from .store import default_store

STATIC = Path(__file__).resolve().parent / "static"
MAX_ANSWER = 1500


def default_grader():
    bedrock = BedrockGrader(lambda prompt: make_agent(prompt, model=make_model(
        os.environ.get("SPRINTZERO_GRADER_MODEL"), temperature=0.0)))
    return FallbackGrader(DeciderGrader(), bedrock) if os.environ.get("STRANDS_DECIDER_URL") else bedrock


def memory_agent_factory(sid: str) -> Callable[[str, str], Any]:
    """Each teammate remembers the session through a Strands session manager (S3 in production)."""
    from strands import Agent
    from strands.agent.conversation_manager import SlidingWindowConversationManager
    bucket = os.environ.get("SPRINTZERO_MEMORY_BUCKET")

    def factory(prompt: str, name: str):
        key = f"{sid}-{name.lower().replace(' ', '-')}"
        if bucket:
            from strands.session.s3_session_manager import S3SessionManager
            manager = S3SessionManager(session_id=key, bucket=bucket, prefix="agents/")
        else:
            from strands.session.file_session_manager import FileSessionManager
            manager = FileSessionManager(session_id=key, storage_dir=os.environ.get("SPRINTZERO_DATA", ".sprintzero"))
        return Agent(model=make_model(), system_prompt=prompt, name=name, callback_handler=None,
                     session_manager=manager, conversation_manager=SlidingWindowConversationManager(window_size=8))
    return factory


class Start(BaseModel):
    pack: str = "flood-alert"


class Answer(BaseModel):
    step: int
    answer: Any
    help_used: bool = False


def create_app(grader=None, agent_factory_for=memory_agent_factory, store=None) -> FastAPI:
    app = FastAPI(title="Sprint Zero")
    team = load_team()
    packs = {p.parent.name: load_pack(p, team) for p in sorted(PACKS_DIR.glob("*/pack.yaml"))}
    grader = grader or default_grader()
    store = store or default_store()

    def session_for(sid: str, record: dict[str, Any]) -> Session:
        pack = packs[record["state"]["pack"]]
        return Session(pack, team, grader, Cast(pack, team, agent_factory_for(sid)), record["state"])

    def public_pack(pack: dict[str, Any]) -> dict[str, Any]:
        return {"id": pack["id"], "title": pack["title"], "tagline": pack["tagline"],
                "product": {"name": pack["product"]["name"], "summary": " ".join(pack["product"]["summary"].split())},
                "sprint_days": pack["sprint_days"], "capacity": pack["capacity_points"],
                "definition_of_done": pack.get("definition_of_done", []),
                "backlog": [{k: b.get(k) for k in ("id", "title", "value", "points")} for b in pack["backlog"]],
                "stakeholders": [{k: s[k] for k in ("id", "name", "role")} for s in pack["stakeholders"]]}

    def step_message(step: dict[str, Any]) -> dict[str, Any] | None:
        if step["kind"] == "text":
            return {"type": "prompt", "day": step["day"], "title": step["title"], "speaker": step["speaker"],
                    "text": step["text"], "prompt": step["prompt"]}
        if step["kind"] == "planning":
            return {"type": "system", "day": step.get("day", 0), "title": step["title"], "text": step.get("prompt", "")}
        return None

    def view(sid: str, record: dict[str, Any]) -> dict[str, Any]:
        s = session_for(sid, record)
        log = {e["step"]: e for e in s.state["log"]}
        return {"id": sid, "pack": public_pack(s.pack),
                "team": {"scrum_master": {k: team["scrum_master"][k] for k in ("id", "name", "role")},
                         "developers": [{k: d[k] for k in ("id", "name", "role")} for d in team["developers"]]},
                "step": s.current(), "feed": record["feed"], "selected": s.state["selected"],
                "grader": getattr(grader, "name", "grader"),
                "product_goal": log.get("briefing", {}).get("answer"),
                "sprint_goal": log.get("sprint_goal", {}).get("answer"),
                "result": s.result() if s.finished else None}

    @app.get("/api/packs")
    def list_packs():
        return [{"id": p["id"], "title": p["title"], "tagline": p["tagline"]} for p in packs.values()]

    @app.post("/api/sessions")
    def start(body: Start):
        if body.pack not in packs:
            raise HTTPException(404, "unknown scenario pack")
        sid = uuid.uuid4().hex
        s = Session(packs[body.pack], team, grader, None)
        record = {"state": s.state, "feed": [m for m in [step_message(s.current())] if m]}
        store.put(sid, record)
        return view(sid, record)

    @app.get("/api/sessions/{sid}")
    def get(sid: str):
        record = store.get(sid)
        if not record:
            raise HTTPException(404, "session not found")
        return view(sid, record)

    @app.post("/api/sessions/{sid}/answer")
    def answer(sid: str, body: Answer):
        record = store.get(sid)
        if not record:
            raise HTTPException(404, "session not found")
        if body.step != record["state"]["step"] + 1:
            raise HTTPException(409, "this step was already answered; reload to continue")
        if isinstance(body.answer, str) and len(body.answer) > MAX_ANSWER:
            raise HTTPException(422, f"keep answers under {MAX_ANSWER} characters")
        s = session_for(sid, record)
        step = s.current()
        try:
            result = s.submit(body.answer, help_used=body.help_used)
        except SessionError as exc:
            raise HTTPException(422, str(exc))
        feed = record["feed"]
        if step["kind"] == "quiz":
            feed.append({"type": "quiz", "title": step["title"], "skipped": result.get("skipped", False),
                         "correct": result.get("correct"), "of": result["of"]})
        else:
            said = body.answer if step["kind"] == "text" else result["planning"]
            feed.append({"type": "you", "kind": step["kind"], "answer": said})
            feed.extend({"type": "reaction", **r} for r in result["reactions"])
            feed.append({"type": "coach", "text": result["coach"], "grade": result["grade"],
                         "competency": result["competency"], "ideal": result.get("ideal", "")})
        message = step_message(result["next"])
        if message:
            feed.append(message)
        record["state"] = s.state
        store.put(sid, record)
        return view(sid, record)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
