"""Tests for Agent CRUD API and workspace isolation."""
from pathlib import Path

import pytest


@pytest.fixture
async def crew_id(client):
    r = await client.post("/api/crews", json={"name": "AgentTestCrew", "description": "test"})
    return r.json()["id"]


class TestAgentCreate:
    async def test_create_agent_basic(self, client, crew_id):
        r = await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "分析师", "role": "数据分析", "order": 0
        })
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "分析师"
        assert data["role"] == "数据分析"
        assert data["crew_id"] == crew_id

    async def test_create_agent_with_system_prompt(self, client, crew_id):
        r = await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "Writer", "role": "Writer", "system_prompt": "You are a writer.", "order": 1
        })
        assert r.status_code == 201
        assert r.json()["system_prompt"] == "You are a writer."

    async def test_create_agent_creates_workspace(self, client, crew_id):
        r = await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "WorkspaceAgent", "role": "测试", "order": 0
        })
        data = r.json()
        ws_path = Path(f"test_workspace/{crew_id}_AgentTestCrew/00_WorkspaceAgent")
        assert ws_path.is_dir()
        assert (ws_path / "README.txt").exists()

    async def test_create_agent_isolated_workspaces(self, client, crew_id):
        r1 = await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "AgentA", "role": "A", "order": 0
        })
        r2 = await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "AgentB", "role": "B", "order": 1
        })
        ws_a = Path(f"test_workspace/{crew_id}_AgentTestCrew/00_AgentA")
        ws_b = Path(f"test_workspace/{crew_id}_AgentTestCrew/01_AgentB")
        assert ws_a.is_dir()
        assert ws_b.is_dir()
        assert ws_a != ws_b

    async def test_create_agent_crew_not_found(self, client):
        r = await client.post("/api/crews/99999/agents", json={
            "name": "X", "role": "X", "order": 0
        })
        assert r.status_code == 404


class TestAgentUpdate:
    async def test_update_agent(self, client, crew_id):
        r = await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "Old", "role": "Old", "order": 0
        })
        agent_id = r.json()["id"]

        r = await client.put(f"/api/agents/{agent_id}", json={
            "name": "New", "role": "NewRole", "system_prompt": "Updated prompt"
        })
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "New"
        assert data["role"] == "NewRole"
        assert data["system_prompt"] == "Updated prompt"

    async def test_update_agent_partial(self, client, crew_id):
        r = await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "Partial", "role": "Test", "order": 0
        })
        agent_id = r.json()["id"]
        r = await client.put(f"/api/agents/{agent_id}", json={"name": "Renamed"})
        assert r.status_code == 200
        assert r.json()["name"] == "Renamed"
        assert r.json()["role"] == "Test"  # unchanged

    async def test_update_agent_not_found(self, client):
        r = await client.put("/api/agents/99999", json={"name": "X"})
        assert r.status_code == 404


class TestAgentDelete:
    async def test_delete_agent(self, client, crew_id):
        r = await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "ToDelete", "role": "Test", "order": 0
        })
        agent_id = r.json()["id"]
        r = await client.delete(f"/api/agents/{agent_id}")
        assert r.status_code == 204

    async def test_delete_agent_removes_workspace(self, client, crew_id):
        r = await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "CleanMe", "role": "Test", "order": 0
        })
        data = r.json()
        ws_path = Path(f"test_workspace/{crew_id}_AgentTestCrew/00_CleanMe")
        assert ws_path.is_dir()
        await client.delete(f"/api/agents/{data['id']}")
        assert not ws_path.exists()

    async def test_delete_agent_not_found(self, client):
        r = await client.delete("/api/agents/99999")
        assert r.status_code == 404

    async def test_agents_visible_in_crew(self, client, crew_id):
        await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "A1", "role": "R1", "order": 0
        })
        await client.post(f"/api/crews/{crew_id}/agents", json={
            "name": "A2", "role": "R2", "order": 1
        })
        r = await client.get(f"/api/crews/{crew_id}")
        assert len(r.json()["agents"]) == 2
        assert r.json()["agents"][0]["name"] == "A1"
        assert r.json()["agents"][1]["name"] == "A2"
