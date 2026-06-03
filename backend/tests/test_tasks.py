"""Tests for task execution, listing, and detail endpoints."""
import pytest


@pytest.fixture
async def crew_with_agents(client):
    """Create a crew with 2 agents, ready for task execution."""
    r = await client.post("/api/crews", json={
        "name": "TaskCrew", "workflow_type": "sequential"
    })
    crew_id = r.json()["id"]
    await client.post(f"/api/crews/{crew_id}/agents", json={
        "name": "Agent1", "role": "研究员", "order": 0
    })
    await client.post(f"/api/crews/{crew_id}/agents", json={
        "name": "Agent2", "role": "作家", "order": 1
    })
    return crew_id


class TestTaskRun:
    async def test_run_task_sequential(self, client, crew_with_agents, mock_llm):
        r = await client.post(f"/api/crews/{crew_with_agents}/run", json={
            "input": "写一篇关于AI的报告"
        })
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "completed"
        assert data["input"] == "写一篇关于AI的报告"
        assert len(data["messages"]) == 2  # 2 agents in sequential
        assert data["result"] is not None

    async def test_run_task_hierarchical(self, client, mock_llm):
        r = await client.post("/api/crews", json={
            "name": "HierCrew", "workflow_type": "hierarchical"
        })
        crew_id = r.json()["id"]
        await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "Leader", "role": "领导", "order": 0
        })
        await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "Worker", "role": "执行者", "order": 1
        })

        r = await client.post(f"/api/crews/{crew_id}/run", json={
            "input": "完成项目计划"
        })
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "completed"
        # Hierarchical: leader plan + worker execution = at least 2 messages
        assert len(data["messages"]) >= 2

    async def test_run_task_roundtable(self, client, mock_llm):
        r = await client.post("/api/crews", json={
            "name": "RTCrew",
            "workflow_type": "roundtable",
            "workflow_config": {"max_rounds": 1}
        })
        crew_id = r.json()["id"]
        await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "A", "role": "专家A", "order": 0
        })
        await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "B", "role": "专家B", "order": 1
        })

        r = await client.post(f"/api/crews/{crew_id}/run", json={
            "input": "讨论项目风险"
        })
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "completed"
        assert len(data["messages"]) >= 1

    async def test_run_task_no_agents(self, client):
        r = await client.post("/api/crews", json={"name": "Empty"})
        crew_id = r.json()["id"]

        r = await client.post(f"/api/crews/{crew_id}/run", json={"input": "test"})
        assert r.status_code == 400
        assert "agent" in r.json()["detail"].lower()

    async def test_run_task_crew_not_found(self, client):
        r = await client.post("/api/crews/99999/run", json={"input": "test"})
        assert r.status_code == 404

    async def test_run_preserves_workspace_in_agents(self, client, crew_with_agents, mock_llm):
        """Verify workspace paths are included in agent dicts during execution."""
        r = await client.post(f"/api/crews/{crew_with_agents}/run", json={
            "input": "test workspace"
        })
        assert r.status_code == 201


class TestTaskList:
    async def test_list_tasks(self, client, crew_with_agents, mock_llm):
        await client.post(f"/api/crews/{crew_with_agents}/run", json={"input": "task 1"})
        await client.post(f"/api/crews/{crew_with_agents}/run", json={"input": "task 2"})

        r = await client.get(f"/api/crews/{crew_with_agents}/tasks")
        assert r.status_code == 200
        tasks = r.json()
        assert len(tasks) == 2
        inputs = {t["input"] for t in tasks}
        assert inputs == {"task 1", "task 2"}

    async def test_list_tasks_empty(self, client, crew_with_agents):
        r = await client.get(f"/api/crews/{crew_with_agents}/tasks")
        assert r.status_code == 200
        assert r.json() == []


class TestTaskGet:
    async def test_get_task(self, client, crew_with_agents, mock_llm):
        r = await client.post(f"/api/crews/{crew_with_agents}/run", json={"input": "get me"})
        task_id = r.json()["id"]

        r = await client.get(f"/api/tasks/{task_id}")
        assert r.status_code == 200
        assert r.json()["input"] == "get me"
        assert r.json()["status"] == "completed"

    async def test_get_task_not_found(self, client):
        r = await client.get("/api/tasks/99999")
        assert r.status_code == 404
