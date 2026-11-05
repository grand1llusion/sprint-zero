# Sprint Zero: practise your first Scrum team before your first day

*Description (1–2 sentences):* A free Scrum team simulator for community-college students and career changers.
You play the Product Owner for one Sprint; an AI Scrum Master and seven AI developers, each a Strands agent with
their own personality, react the way a real team would, and a coach shows you what to try next.

**Demo video:** https://youtu.be/Mif7gT-GCiY  
**Code:** https://github.com/grand1llusion/sprint-zero  
**Focus area:** Education

## The problem

Most people meet Scrum for the first time on the job. Community-college programs, high schools and bootcamps
teach tools and languages, but rarely how a team actually plans and delivers work: who decides what gets built,
what a Sprint Goal is for, what to say when a stakeholder demands a feature mid-Sprint, or why "basically done"
isn't done. Paid Scrum courses exist, but they cost money and assume you already work in tech. So new hires walk
into their first sprint planning guessing, and the people with the least access to training guess the most.

Sprint Zero gives them a safe place to practise that first Sprint before it counts.

## What it does

You are the Product Owner of **RiverWatch Alerts**, a text-message flood warning for a rural county, so even the
practice product is one that would help people. In about 20 minutes you:

1. **Learn the basics first.** A short walkthrough covers the three Scrum roles, the events and the artifacts,
   says how long the session takes, and shows you the screen. No questions up front; a five-question warm-up is
   optional and skippable.
2. **Set the Product Goal** after a briefing from the county's emergency manager.
3. **Plan the Sprint.** Choose backlog items within the team's capacity. A "Learn as you go" card explains how
   to read a backlog item (ID, value, story points, what "??" means) and what your job is.
4. **Handle five days of real situations, in your own words:** the county commissioner promises the board a
   dashboard by Friday, the tester can't test "make it user friendly", the junior developer is quietly stuck,
   the flood forecast moves up, and a developer wants to call untested work "basically done".
5. **Get a debrief:** a result for each Product Owner skill, and your quick-check score before and after.

After every answer, the people your decision affects react in character, and Sam, the Scrum Master, coaches you:
what worked, one thing to improve, and the principle behind it. A **HELP** button fills in a fill-in-the-blank
starter (not the answer) for anyone stuck on a blank page.

## The team: nine Strands agents

| | Name | Role | How they test you |
|---|---|---|---|
| 🧭 | Sam Whitfield | Scrum Master | Coaches you, never decides for you |
| 1 | Priya Raman | Tech lead | Protects focus; asks "what problem are we solving?" |
| 2 | Marcus Bell | Backend developer | "Easy, two points." Underestimates everything |
| 3 | Sofia Alvarez | Frontend developer | Pushes for accessibility, slow phones and Spanish |
| 4 | Kenji Watanabe | QA engineer | Won't test a story without acceptance criteria |
| 5 | Dana Okafor | DevOps engineer | Cost, reliability and who gets paged at 2 a.m. |
| 6 | Leah Morgan | UX designer | "Have we asked a real user?" |
| 7 | Jordan Reyes | Junior developer | Gets stuck quietly: the learner's mirror |

Plus two stakeholders: Rosa, the emergency manager, and Commissioner Pruitt.

## How it's built

- **Strands Agents SDK.** Every person is their own Strands `Agent` on **Amazon Bedrock** (Amazon Nova), with a
  persona prompt, pack-specific context and their own memory of the session. Memory persists between web
  requests through Strands **session managers**: files locally, **Amazon S3** in production.
- **A sprint engine in plain code** owns the days, the state and the order of events. The agents only react.
  For each event the engine picks the one to three people it affects, never all nine, so a session stays fast
  and affordable enough to serve many learners. Over a whole Sprint, every developer gets a turn.
- **Grading with Strands Decider 2B.** Each free-text answer is graded against the scenario's rubric (strong,
  partial, weak or off topic) with one typed `choice` question, which returns a calibrated confidence;
  low-confidence grades are flagged. If the Decider server is unavailable, a Bedrock model grades against the
  same rubric. Grades are labels, never scores.
- **Personas react to consequences, not scores.** A weak decision tells the affected developer "this creates a
  real problem for you, push back in character", so the feedback feels like a team, not a quiz.
- **Deterministic scoring.** Plain code turns grades into a result for each competency, and any run can be
  re-scored from its decision log alone.
- **Scenario packs are data.** The product, backlog, injects, rubrics, coaching points, HELP starters and quiz
  live in one YAML file; a shared glossary of 22 plain-language Scrum terms feeds the "Learn as you go" cards.
  A new scenario (a clinic finder, a food bank, a Military-to-Agile pack) needs no code changes.
- **Built to serve real users.** A FastAPI web app with a stateless server: sessions can live in **Amazon
  DynamoDB**, agent memory in **S3**. The demo runs on **Amazon EC2** next to a Strands Decider 2B server.
- **Tested offline:** 27 tests with scripted Strands models and a fake grader cover the engine, grading, routing,
  scoring replay, the steering hook, the glossary tool and the web API.

## From the workshop to Sprint Zero

I completed *Building AI Agents with Strands SDK: From Simple Loops to Multi-Agent Swarms* (all seven modules,
including the optional multi-agent and evals modules), then pushed each idea further:

| Workshop module | What it taught | How Sprint Zero uses or extends it |
|---|---|---|
| 1. Agent loop and tools | One agent, a system prompt, Amazon Bedrock, a `@tool` | Nine agents, each with its own persona and scenario context; Sam, the Scrum Master, has a `define_term` `@tool` so coaching uses the glossary's vetted wording |
| 2–3. Hooks and steering | Deterministic control around a model | A `StayInCharacter` `HookProvider` on every teammate: after each model call, plain-code rules check the line (no "as an AI", no scores, no lists or emojis, short dialogue) and set `retry` so Strands asks again. At the app level, plain code also owns the timeline, routing and scoring |
| 4. Session managers | `FileSessionManager` persists one conversation | One persisted memory per teammate per learner (files locally, S3 in production), so a stateless web server can serve many learners |
| 6. Multi-agent | An orchestrator delegates to a specialist | A code-owned sprint engine is the orchestrator: for every event it picks the one to three teammates the decision affects, and each hears what the others said |
| 7. Evals | Score responses against a rubric | Every learner answer is scored against the scenario's rubric, by Strands Decider 2B with a calibrated confidence, or a Bedrock model as backup |
| 5. AgentCore | Managed deployment | Next step: the web app runs on EC2 today; AgentCore Runtime is the planned serverless home |

## Measuring improvement

Sprint Zero measures learning in three ways, all stored with each session:

- the same five-question check before and after (optional, so beginners aren't put off);
- a result for each of eight Product Owner competencies, comparable across replays;
- how often the learner needed HELP, which should fall with practice.

I haven't run a pilot with learners yet, so I'm not reporting outcome numbers. The next step is a small pilot with
community-college students, comparing first and second runs.

## What I learned

1. **Beginners need the vocabulary before the decision.** My first playtest of Sprint Planning showed it: without
   knowing what a backlog item's ID, value or story points mean, a newcomer is lost. That led to the "Learn as you
   go" cards and the labelled backlog: definitions only, so the decision is still theirs.
2. **Don't open with a test.** The first version started with five quiz questions. For someone who has never seen
   Scrum, that's a wall. A walkthrough first, then an optional warm-up, is far friendlier.
3. **Help should teach, not answer.** HELP inserts a frame with blanks ("This Sprint the team is committed to
   [our Sprint Goal]…"), and the full strong answer only appears after you submit.
4. **Show what the AI is doing.** A few seconds of silence feels broken. A live status ("Allowing Strands to weigh
   the option…", then the grader in use and who is reading your message) makes the wait part of the experience.
5. **Let code own the state.** Agents are great at sounding like people and poor at keeping score. Keeping the
   timeline, routing and scoring in plain code made the agents more reliable, not less.

## What's next

More scenario packs (clinic finder, food bank volunteers, Military-to-Agile for transitioning service members),
serverless hosting, and a pilot with learners to measure the before-and-after.

**Try it step by step:** the repo's `notebooks/sprint_zero_walkthrough.ipynb` rebuilds the team module by module, in the workshop's order, and runs in Amazon SageMaker or with no AWS access at all.

**Built with:** Strands Agents SDK, Amazon Bedrock, Strands Decider 2B, Amazon EC2, Amazon S3, Amazon DynamoDB.
All people and places are fictional. The video narration uses an AI-generated voice.
