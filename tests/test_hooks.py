"""The Strands hook and tool the cast uses: StayInCharacter steering and the define_term glossary tool."""
from strands import Agent

from sprintzero.agents import teammate_extras
from sprintzero.hooks import StayInCharacter, check_reply, define_term
from test_sprint_zero import ScriptedModel


def test_hook_retries_a_line_that_breaks_character():
    model = ScriptedModel(["As an AI, I'd give that answer a strong score! 🎉", "Honestly, that helps me a lot."])
    hook = StayInCharacter()
    agent = Agent(model=model, system_prompt="You are Priya.", name="Priya Raman", callback_handler=None, hooks=[hook])
    reply = str(agent("The Product Owner said: let's keep the Sprint Goal.")).strip()
    assert reply == "Honestly, that helps me a lot."
    assert len(model.seen) == 2                                  # Strands discarded the first reply and asked again
    assert hook.log[0]["agent"] == "Priya Raman"
    assert set(hook.log[0]["problems"]) >= {"mentions being an AI", "uses emojis"}
    assert "As an AI" not in str(agent.messages)                 # the broken line never enters memory


def test_hook_retries_at_most_once_per_turn():
    model = ScriptedModel(["- a list", "- still a list", "Fine by me."])
    agent = Agent(model=model, system_prompt="x", callback_handler=None, hooks=[StayInCharacter(max_retries=1)])
    assert str(agent("hi")).strip() == "- still a list"         # gives up after one retry rather than looping
    assert str(agent("again")).strip() == "Fine by me."         # and resets for the next turn


def test_good_lines_pass_untouched():
    assert check_reply("That works for me, but who checks the Spanish text?", 600) == []
    model = ScriptedModel(["That works for me."])
    agent = Agent(model=model, system_prompt="x", callback_handler=None, hooks=[StayInCharacter()])
    agent("hi")
    assert len(model.seen) == 1


def test_define_term_reads_the_glossary():
    assert define_term._tool_func("Product Owner").startswith("Product Owner: The person accountable")
    assert define_term._tool_func("sprint goal").startswith("Sprint Goal:")
    assert "not in the glossary" in define_term._tool_func("velocity hacking")


def test_only_the_scrum_master_gets_the_tool():
    assert [t.tool_name for t in teammate_extras("Sam Whitfield")["tools"]] == ["define_term"]
    assert "tools" not in teammate_extras("Marcus Bell")
    assert isinstance(teammate_extras("Marcus Bell")["hooks"][0], StayInCharacter)
