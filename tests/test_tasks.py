"""Tests for task execution, listing, and detail endpoints."""
import pytest


@pytest.fixture
async def with_agents(client):
    """Add two agents to the default crew."""
    await client.post("/api/agents", json={
        "name": "Agent1", "role": "研究员", "order": 0
    })
    await client.post("/api/agents", json={
        "name": "Agent2", "role": "作家", "order": 1
    })


class TestTaskRun:
    async def test_run_task_sequential(self, client, with_agents, mock_llm):
        # Default crew is roundtable, so test via roundtable path
        r = await client.post("/api/run", json={"input": "写一篇关于AI的报告"})
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "completed"
        assert data["input"] == "写一篇关于AI的报告"
        assert len(data["messages"]) >= 1
        assert data["result"] is not None

    async def test_run_task_no_agents(self, client, mock_llm):
        """Default crew exists but has no agents after cleanup."""
        r = await client.post("/api/run", json={"input": "test"})
        assert r.status_code == 400
        assert "agent" in r.json()["detail"].lower()


class TestTaskList:
    async def test_list_tasks(self, client, with_agents, mock_llm):
        await client.post("/api/run", json={"input": "task 1"})
        await client.post("/api/run", json={"input": "task 2"})

        r = await client.get("/api/tasks")
        assert r.status_code == 200
        tasks = r.json()
        assert len(tasks) == 2
        inputs = {t["input"] for t in tasks}
        assert inputs == {"task 1", "task 2"}

    async def test_list_tasks_empty(self, client):
        r = await client.get("/api/tasks")
        assert r.status_code == 200
        assert r.json() == []


class TestTaskGet:
    async def test_get_task(self, client, with_agents, mock_llm):
        r = await client.post("/api/run", json={"input": "get me"})
        task_id = r.json()["id"]

        r = await client.get(f"/api/tasks/{task_id}")
        assert r.status_code == 200
        assert r.json()["input"] == "get me"
        assert r.json()["status"] == "completed"

    async def test_get_task_not_found(self, client):
        r = await client.get("/api/tasks/99999")
        assert r.status_code == 404
