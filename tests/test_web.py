"""The web API, driven end to end with the scripted cast and a fake grader."""
from fastapi.testclient import TestClient
from strands import Agent

from sprintzero.web.server import create_app
from sprintzero.web.store import MemoryStore
from test_sprint_zero import PACK, PERFECT_QUIZ, FakeGrader, ScriptedModel


def client():
    factory_for = lambda sid: (lambda prompt, name: Agent(model=ScriptedModel(), system_prompt=prompt, name=name,
                                                          callback_handler=None))
    return TestClient(create_app(grader=FakeGrader(), agent_factory_for=factory_for, store=MemoryStore()))


def answer(c, v, value):
    r = c.post(f"/api/sessions/{v['id']}/answer", json={"step": v["step"]["number"], "answer": value})
    assert r.status_code == 200, r.text
    return r.json()


def test_a_whole_session_over_http():
    c = client()
    assert c.get("/").status_code == 200 and c.get("/static/app.js").status_code == 200
    v = c.post("/api/sessions", json={"pack": "flood-alert"}).json()
    assert v["step"]["kind"] == "quiz" and len(v["team"]["developers"]) == 7
    v = answer(c, v, [0] * 5)
    assert v["step"]["help"] and v["grader"] == "fake"
    r = c.post(f"/api/sessions/{v['id']}/answer", json={"step": v["step"]["number"], "help_used": True,
                                                       "answer": "Every resident in a flood zone gets a warning on any phone."})
    v = r.json()
    assert v["product_goal"] and v["step"]["kind"] == "planning"
    v = answer(c, v, ["B1", "B2", "B6", "B3"])
    assert v["selected"] == ["B1", "B2", "B6", "B3"]
    v = answer(c, v, "Residents can sign up, receive a warning and opt out.")
    for _ in PACK["injects"]:
        v = answer(c, v, "I would keep the Sprint Goal and put it on the backlog to order later.")
    v = answer(c, v, PERFECT_QUIZ)
    assert v["step"]["kind"] == "debrief" and v["result"]["medal"] == "Gold"
    kinds = [m["type"] for m in v["feed"]]
    assert kinds.count("coach") == 3 + len(PACK["injects"]) and "reaction" in kinds
    # reloading the page gets the same session back
    assert c.get(f"/api/sessions/{v['id']}").json()["result"]["medal"] == "Gold"


def test_double_submit_and_bad_input_are_refused():
    c = client()
    v = c.post("/api/sessions", json={}).json()
    stale = v["step"]["number"]
    v = answer(c, v, [0] * 5)
    r = c.post(f"/api/sessions/{v['id']}/answer", json={"step": stale, "answer": [0] * 5})
    assert r.status_code == 409
    r = c.post(f"/api/sessions/{v['id']}/answer", json={"step": v["step"]["number"], "answer": "x" * 2000})
    assert r.status_code == 422
    assert c.get("/api/sessions/nope").status_code == 404
    assert c.post("/api/sessions", json={"pack": "nope"}).status_code == 404
