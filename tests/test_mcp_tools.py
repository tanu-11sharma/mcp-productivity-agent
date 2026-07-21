from app.mcp_tools import call_tool, list_tool_specs
from app.store import ProductivityStore


def test_list_tool_specs_exposes_all_tools():
    specs = list_tool_specs()
    names = {s["name"] for s in specs}
    assert names == {
        "list_tasks",
        "create_task",
        "complete_task",
        "create_note",
        "search_notes",
    }
    for spec in specs:
        assert "description" in spec
        assert "input_schema" in spec


def test_create_and_list_tasks():
    store = ProductivityStore()
    before = len(store.list_tasks())

    result = call_tool(store, "create_task", {"title": "Write tests", "priority": "high"})
    assert result.ok
    assert result.data["title"] == "Write tests"
    assert result.data["priority"] == "high"

    after = call_tool(store, "list_tasks", {})
    assert after.ok
    assert len(after.data) == before + 1


def test_create_task_rejects_bad_priority():
    store = ProductivityStore()
    result = call_tool(store, "create_task", {"title": "x", "priority": "urgent!!"})
    assert not result.ok
    assert "priority" in result.error


def test_complete_task_unknown_id_errors():
    store = ProductivityStore()
    result = call_tool(store, "complete_task", {"task_id": 9999})
    assert not result.ok
    assert "9999" in result.error


def test_complete_task_marks_done_and_excluded_from_default_list():
    store = ProductivityStore()
    created = call_tool(store, "create_task", {"title": "temp task"})
    task_id = created.data["id"]

    completed = call_tool(store, "complete_task", {"task_id": task_id})
    assert completed.ok
    assert completed.data["done"] is True

    open_tasks = call_tool(store, "list_tasks", {})
    assert all(t["id"] != task_id for t in open_tasks.data)

    all_tasks = call_tool(store, "list_tasks", {"include_done": True})
    assert any(t["id"] == task_id for t in all_tasks.data)


def test_create_and_search_notes():
    store = ProductivityStore()
    call_tool(store, "create_note", {"title": "Retro", "body": "Ship faster next sprint", "tags": ["retro"]})

    hits = call_tool(store, "search_notes", {"query": "faster"})
    assert hits.ok
    assert len(hits.data) == 1
    assert hits.data[0]["title"] == "Retro"

    misses = call_tool(store, "search_notes", {"query": "nonexistent-topic"})
    assert misses.ok
    assert misses.data == []


def test_unknown_tool_returns_error_not_exception():
    store = ProductivityStore()
    result = call_tool(store, "delete_everything", {})
    assert not result.ok
    assert "unknown tool" in result.error
