"""Tests for Agent CRUD API and workspace isolation."""
from pathlib import Path

import pytest


class TestAgentCreate:
    async def test_create_agent_basic(self, client):
        r = await client.post("/api/agents", json={
            "name": "分析师", "role": "数据分析", "order": 0
        })
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "分析师"
        assert data["role"] == "数据分析"

    async def test_create_agent_with_system_prompt(self, client):
        r = await client.post("/api/agents", json={
            "name": "Writer", "role": "Writer", "system_prompt": "You are a writer.", "order": 1
        })
        assert r.status_code == 201
        assert r.json()["system_prompt"] == "You are a writer."

    async def test_create_agent_creates_workspace(self, client):
        r = await client.post("/api/agents", json={
            "name": "WorkspaceAgent", "role": "测试", "order": 0
        })
        assert r.status_code == 201
        ws_path = Path("test_workspace/00_WorkspaceAgent")
        assert ws_path.is_dir()
        assert (ws_path / "README.txt").exists()

    async def test_create_agent_isolated_workspaces(self, client):
        r1 = await client.post("/api/agents", json={
            "name": "AgentA", "role": "A", "order": 0
        })
        r2 = await client.post("/api/agents", json={
            "name": "AgentB", "role": "B", "order": 1
        })
        ws_a = Path("test_workspace/00_AgentA")
        ws_b = Path("test_workspace/01_AgentB")
        assert ws_a.is_dir()
        assert ws_b.is_dir()
        assert ws_a != ws_b


class TestAgentList:
    async def test_list_agents_empty(self, client):
        r = await client.get("/api/agents")
        assert r.status_code == 200
        assert r.json() == []

    async def test_list_agents_multiple(self, client):
        await client.post("/api/agents", json={"name": "A1", "role": "R1", "order": 0})
        await client.post("/api/agents", json={"name": "A2", "role": "R2", "order": 1})
        r = await client.get("/api/agents")
        assert r.status_code == 200
        agents = r.json()
        assert len(agents) == 2
        assert agents[0]["name"] == "A1"
        assert agents[1]["name"] == "A2"


class TestAgentUpdate:
    async def test_update_agent(self, client):
        r = await client.post("/api/agents", json={
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

    async def test_update_agent_partial(self, client):
        r = await client.post("/api/agents", json={
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
    async def test_delete_agent(self, client):
        r = await client.post("/api/agents", json={
            "name": "ToDelete", "role": "Test", "order": 0
        })
        agent_id = r.json()["id"]
        r = await client.delete(f"/api/agents/{agent_id}")
        assert r.status_code == 204

    async def test_delete_agent_removes_workspace(self, client):
        r = await client.post("/api/agents", json={
            "name": "CleanMe", "role": "Test", "order": 0
        })
        assert r.status_code == 201
        ws_path = Path("test_workspace/00_CleanMe")
        assert ws_path.is_dir()
        await client.delete(f"/api/agents/{r.json()['id']}")
        assert not ws_path.exists()

    async def test_delete_agent_not_found(self, client):
        r = await client.delete("/api/agents/99999")
        assert r.status_code == 404
