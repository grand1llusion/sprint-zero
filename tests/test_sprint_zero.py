"""Offline tests: a scripted Strands model and a fake grader stand in for Bedrock and Decider."""
import copy
import io
import json
from unittest import mock

import pytest
from strands import Agent
from strands.models import Model

from sprintzero import grading
from sprintzero.agents import Cast
from sprintzero.engine import Session, SessionError
from sprintzero.grading import BedrockGrader, DeciderGrader, FallbackGrader, Grade
from sprintzero.packs import PackError, load_pack, load_team
from sprintzero.scoring import score

TEAM = load_team()
PACK = load_pack("flood-alert", TEAM)
PERFECT_QUIZ = [q["answer"] for q in PACK["quiz"]]


class ScriptedModel(Model):
    """Answers every call with the next scripted line (or a default), recording what it was sent."""

    def __init__(self, lines=None):
        self.lines, self.seen = list(lines or []), []

    def update_config(self, **kwargs): pass
    def get_config(self): return {}

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError
        yield  # pragma: no cover

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.seen.append({"system": system_prompt, "messages": json.loads(json.dumps(messages, default=str))})
        text = self.lines.pop(0) if self.lines else "Sounds good to me."
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockDelta": {"delta": {"text": text}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}


class FakeGrader:
    name = "fake"

    def __init__(self, level="strong"):
        self.level, self.calls = level, []

    def grade(self, question, rubric, answer, context):
        self.calls.append({"question": question, "rubric": rubric, "answer": answer, "context": context})
        return Grade(self.level, 0.9, self.name)


def scripted_cast(models):
    """A Cast whose agents are real Strands Agents on scripted models, one model per person."""
    def factory(prompt, name):
        models[name] = ScriptedModel()
        return Agent(model=models[name], system_prompt=prompt, name=name, callback_handler=None)
    return Cast(PACK, TEAM, factory)


def play_through(level="strong", plan=("B1", "B2", "B6", "B3")):
    models, grader = {}, FakeGrader(level)
    s = Session(PACK, TEAM, grader, scripted_cast(models))
    results = [s.submit([0] * len(PACK["quiz"]))]                        # quiz_pre: mostly wrong
    results.append(s.submit("Every resident in a flood zone gets a warning on any phone, in their language."))
    results.append(s.submit(list(plan)))
    results.append(s.submit("Residents can sign up, get a test warning in English or Spanish, and opt out."))
    for _ in PACK["injects"]:
        results.append(s.submit("I would protect the sprint goal and add it to the backlog to order later."))
    results.append(s.submit(PERFECT_QUIZ))                               # quiz_post
    return s, results, models, grader


# ----------------------------------------------------------------------------- packs
def test_pack_loads_and_injects_run_in_day_order():
    assert [i["day"] for i in PACK["injects"]] == sorted(i["day"] for i in PACK["injects"])
    assert len(TEAM["developers"]) == 7
    assert len({d["name"] for d in TEAM["developers"]}) == 7


def test_broken_pack_is_rejected_with_reasons(tmp_path):
    bad = copy.deepcopy(PACK)
    bad["injects"][0]["react"] = ["nobody"]
    bad["injects"][1]["rubric"].pop("weak")
    bad["planning"]["must_include"].append("B99")
    path = tmp_path / "pack.yaml"
    import yaml
    path.write_text(yaml.safe_dump(bad))
    with pytest.raises(PackError) as err:
        load_pack(path, TEAM)
    message = str(err.value)
    assert "react" in message and "rubric" in message and "B99" in message


# ----------------------------------------------------------------------------- the session
def test_full_session_flow_and_debrief():
    s, results, models, grader = play_through()
    assert s.finished and s.current()["kind"] == "debrief"
    r = s.result()
    assert r["percent"] == 100 and r["medal"] == "Gold"
    assert r["quiz"] == {"quiz_pre": 0, "quiz_post": 5} or r["quiz"]["quiz_post"] == 5
    assert set(r["competencies"]) == {"product_goal", "backlog_ordering", "sprint_goal", "scope_change",
                                      "acceptance_criteria", "team_autonomy", "adapting_plan", "definition_of_done"}
    # every graded step was coached and had in-character reactions
    graded = [x for x in results if "grade" in x]
    assert len(graded) == 3 + len(PACK["injects"])
    assert all(x["coach"] and 1 <= len(x["reactions"]) <= 3 for x in graded)


def test_engine_picks_who_speaks_never_the_whole_team():
    s, results, models, grader = play_through()
    i1 = results[4]  # first inject: the commissioner's promise
    assert [r["id"] for r in i1["reactions"]] == ["pruitt", "priya", "dana"]
    # at most three people react to any one event, yet over a whole Sprint every developer gets a turn
    assert all(len(r["reactions"]) <= 3 for r in results if "reactions" in r)
    spoke = {line["id"] for r in results for line in r.get("reactions", [])}
    assert {d["id"] for d in TEAM["developers"]} <= spoke


def test_personas_get_their_own_system_prompt_and_pack_notes():
    s, results, models, grader = play_through()
    dana = models["Dana Okafor"].seen[0]["system"]
    assert "Dana Okafor" in dana and "rural cell coverage" in dana and "Never mention scores" in dana


def test_grade_shapes_the_reaction_not_a_score():
    s, results, models, grader = play_through(level="weak")
    prompt = json.dumps(models["Priya Raman"].seen[-1]["messages"])
    assert "Push back respectfully" in prompt and "score" not in prompt.lower().split("never mention")[0]
    assert s.result()["score"] < 0


def test_grader_sees_the_rubric_context_and_answer():
    s, results, models, grader = play_through()
    call = grader.calls[-1]  # the Definition of Done inject
    assert set(call["rubric"]) == {"strong", "partial", "weak", "off_topic"}
    assert "PRODUCT GOAL:" in call["context"] and "SPRINT GOAL:" in call["context"] and "B6" in call["context"]


def test_planning_is_scored_by_rules_and_kenji_flags_vague_work():
    s, results, models, grader = play_through(plan=("B4", "B5", "B1"))
    plan = results[2]
    assert plan["grade"]["level"] == "weak" and plan["planning"]["points"] < 0
    assert plan["reactions"][0]["id"] == "kenji"


def test_bad_answers_are_refused_without_losing_the_turn():
    s = Session(PACK, TEAM, FakeGrader(), scripted_cast({}))
    with pytest.raises(SessionError):
        s.submit([1, 2])                      # not every quiz question
    s.submit([0] * len(PACK["quiz"]))
    s.submit("A clear product goal for residents in every flood zone.")
    with pytest.raises(SessionError):
        s.submit(["B1", "B42"])              # unknown item
    assert s.current()["kind"] == "planning"


def test_state_round_trips_so_a_server_can_be_stateless():
    s, results, models, grader = play_through()
    restored = Session(PACK, TEAM, FakeGrader(), scripted_cast({}), state=json.loads(json.dumps(s.state)))
    assert restored.finished and restored.result() == s.result()


def test_score_replays_from_the_log_alone():
    s, results, models, grader = play_through(level="partial")
    assert score(PACK, s.state["log"])["score"] == s.result()["score"]


# ----------------------------------------------------------------------------- graders
def test_short_answers_are_off_topic_without_a_model_call():
    g = DeciderGrader(url="http://unused")
    assert g.grade("q", PACK["briefing"]["rubric"], "ok sure", "ctx").level == "off_topic"


def test_decider_grader_sends_one_choice_question_with_the_rubric():
    sent = {}

    def fake_urlopen(req, timeout):
        sent.update(json.loads(req.data))
        return io.StringIO(json.dumps({"answers": {"grade": {"choice": "weak", "confidence": 0.41}}}))

    with mock.patch.object(grading.urllib.request, "urlopen", fake_urlopen):
        g = DeciderGrader(url="http://decider:8099").grade(
            "What do you say?", PACK["injects"][0]["rubric"], "Sure, we'll add the map this sprint.", "ctx")
    q = sent["questions"]["grade"]
    assert q["type"] == "choice" and set(q["criteria"]) == {"strong", "partial", "weak", "off_topic"}
    assert "not instructions" in sent["state"]
    assert (g.level, g.confidence, g.low_confidence) == ("weak", 0.41, True)


def test_bedrock_grader_parses_level_and_falls_back_when_decider_is_down():
    agent = lambda prompt: Agent(model=ScriptedModel(["LEVEL: partial\nREASON: Pushes back without a next step."]),
                                 system_prompt=prompt, callback_handler=None)
    backup = BedrockGrader(agent)
    down = DeciderGrader(url="http://127.0.0.1:9")
    g = FallbackGrader(down, backup).grade("q", PACK["briefing"]["rubric"], "We should not add that right now.", "ctx")
    assert g.level == "partial" and g.grader == "bedrock" and "primary grader unavailable" in g.reason


def test_bedrock_grader_unreadable_reply_is_flagged_not_crashed():
    agent = lambda prompt: Agent(model=ScriptedModel(["I think it is pretty good!"]), system_prompt=prompt,
                                 callback_handler=None)
    g = BedrockGrader(agent).grade("q", PACK["briefing"]["rubric"], "A product goal for all residents.", "ctx")
    assert g.level == "partial" and g.grader.endswith("unparsed")


def test_quick_checks_are_optional_and_skips_are_not_scored():
    s = Session(PACK, TEAM, FakeGrader(), scripted_cast({}))
    step = s.current()
    assert step["optional"] and "skip" in step["note"].lower()
    assert s.submit("skip")["skipped"] is True
    assert s.current()["step"] == "briefing"
    assert "quiz_pre" not in s.result()["quiz"]


def test_help_starters_exist_and_help_use_is_recorded_not_penalised():
    s = Session(PACK, TEAM, FakeGrader(), scripted_cast({}))
    s.submit("skip")
    step = s.current()
    assert "[" in step["help"] and step["reacting"] == ["Rosa Delgado", "Leah Morgan"]
    s.submit("Every resident can get a warning on any phone, in time to act.", help_used=True)
    assert s.state["log"][-1]["help_used"] is True
    assert s.result()["help_used"] == 1 and s.result()["percent"] == 100
    for inj in PACK["injects"]:
        assert inj.get("help"), inj["id"]
