# Sprint Zero

**A free Scrum team simulator for people about to join their first team.** You play the Product
Owner. An AI Scrum Master and seven AI developers, each with their own personality, respond the way a
real team would: they push back on vague stories, underestimate, get quietly stuck, and hold you to
the Definition of Done.

Most community-college and high-school graduates walk into their first tech job without ever having
seen how a team plans and delivers work. Sprint Zero lets them practise one Sprint first, safely,
and shows their improvement with a quick check before and after.

## How a session works

1. **Quick check:** five questions, to see where you start.
2. **Briefing:** the sponsor explains the product; you write the Product Goal.
3. **Sprint Planning:** you choose the Sprint's backlog items within the team's capacity.
4. **Sprint Goal:** one sentence for what this Sprint achieves.
5. **Injects, day by day:** a stakeholder makes a promise you can't keep, a story has no acceptance
   criteria, a teammate is quietly stuck, the forecast changes, and "basically done" work appears.
   You type what you would say.
6. **Quick check again, then a debrief** with your result for each Scrum skill.

Each answer is graded against the pack's rubric (strong, partial, weak, off topic), then the people
it affects react in character and Sam, the Scrum Master, coaches you.

## The team

| | Name | Role |
|---|---|---|
| 🧭 | Sam Whitfield | Scrum Master (coach) |
| 1 | Priya Raman | Tech lead |
| 2 | Marcus Bell | Backend developer |
| 3 | Sofia Alvarez | Frontend developer |
| 4 | Kenji Watanabe | QA and test engineer |
| 5 | Dana Okafor | DevOps and cloud engineer |
| 6 | Leah Morgan | UX and product designer |
| 7 | Jordan Reyes | Junior developer |

Personas live in [`packs/team.yaml`](packs/team.yaml). All people and places are fictional.

## How it is built

- **Strands Agents SDK:** every person is a Strands `Agent` on Amazon Bedrock with their own persona
  and memory. The sprint engine chooses who speaks (one to three people per event), so sessions stay
  fast and affordable.
- **The engine is plain code** ([`sprintzero/engine.py`](sprintzero/engine.py)): it owns the days, the
  state and the order of events. Session state is JSON, so a web server can stay stateless.
- **Grading** ([`sprintzero/grading.py`](sprintzero/grading.py)): Strands Decider 2B picks the rubric
  level with a calibrated confidence when a Decider server is available; otherwise a Bedrock model
  grades against the same rubric. Grades are labels, never scores.
- **Scoring is deterministic** ([`sprintzero/scoring.py`](sprintzero/scoring.py)) and re-runs from
  the decision log alone.
- **Scenario packs are data** ([`packs/flood-alert/pack.yaml`](packs/flood-alert/pack.yaml)): the
  product, backlog, injects with rubrics, coaching points and quiz. Write a new YAML file to add a
  scenario; no code changes.

## Play it in AWS CloudShell

You need an AWS account with Amazon Bedrock access to Amazon Nova Lite in us-east-1.

```bash
sudo dnf install -y python3.11 python3.11-pip git
git clone https://github.com/grand1llusion/sprint-zero && cd sprint-zero
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m sprintzero.play
```

Optional: `export STRANDS_DECIDER_URL=http://<host>:8099` to grade with Strands Decider 2B.

## Tests

```bash
pip install pytest && python -m pytest -q
```

The tests run offline with scripted Strands models and a fake grader.

## License

Apache-2.0. Scenario packs and personas are original and fictional.
