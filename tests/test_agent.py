from app.agent import ProductivityAgent
from app.store import ProductivityStore


def make_agent() -> ProductivityAgent:
    return ProductivityAgent(store=ProductivityStore())


def test_list_tasks_intent():
    agent = make_agent()
    response = agent.handle("list tasks")
    assert "Open tasks" in response.reply
    assert len(response.steps) == 1
    assert response.steps[0].tool == "list_tasks"


def test_add_task_intent_parses_priority_and_due():
    agent = make_agent()
    response = agent.handle("add task: Ship release notes priority:high due:2026-07-25")
    assert response.steps[0].tool == "create_task"
    assert response.steps[0].result["data"]["priority"] == "high"
    assert response.steps[0].result["data"]["due"] == "2026-07-25"
    assert "Ship release notes" in response.reply


def test_add_task_then_complete_it():
    agent = make_agent()
    add_response = agent.handle("add task: temp job")
    task_id = add_response.steps[0].result["data"]["id"]

    done_response = agent.handle(f"done {task_id}")
    assert done_response.steps[0].tool == "complete_task"
    assert done_response.steps[0].result["data"]["done"] is True
    assert str(task_id) in done_response.reply


def test_add_note_intent_splits_title_and_body():
    agent = make_agent()
    response = agent.handle("note: Launch checklist | confirm rollback plan is documented")
    step = response.steps[0]
    assert step.tool == "create_note"
    assert step.arguments["title"] == "Launch checklist"
    assert step.arguments["body"] == "confirm rollback plan is documented"


def test_search_notes_intent():
    agent = make_agent()
    agent.handle("note: Retro notes | keep sprints shorter")
    response = agent.handle("search notes shorter")
    assert "Matching notes" in response.reply


def test_daily_briefing_chains_three_tool_calls():
    agent = make_agent()
    response = agent.handle("daily briefing")
    tool_sequence = [s.tool for s in response.steps]
    assert tool_sequence == ["list_tasks", "search_notes", "create_note"]
    # the final step must be ok and produce a saved note
    assert response.steps[-1].result["ok"] is True
    assert "Daily briefing saved" in response.reply


def test_unrecognized_command_gives_help_text():
    agent = make_agent()
    response = agent.handle("do a backflip")
    assert response.steps == []
    assert "didn't recognize" in response.reply
