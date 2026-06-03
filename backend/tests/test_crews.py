"""Tests for Crew CRUD API and workspace integration."""
import os
from pathlib import Path

import pytest


class TestCrewCreate:
    async def test_create_crew_basic(self, client):
        r = await client.post("/api/crews", json={"name": "测试团队"})
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "测试团队"
        assert data["workflow_type"] == "sequential"
        assert data["agents"] == []

    async def test_create_crew_with_description(self, client):
        r = await client.post("/api/crews", json={
            "name": "DevTeam", "description": "开发团队", "workflow_type": "hierarchical"
        })
        assert r.status_code == 201
        data = r.json()
        assert data["description"] == "开发团队"
        assert data["workflow_type"] == "hierarchical"

    async def test_create_crew_creates_workspace(self, client):
        r = await client.post("/api/crews", json={"name": "WorkspaceTeam"})
        data = r.json()
        ws_path = Path(f"test_workspace/{data['id']}_WorkspaceTeam")
        assert ws_path.is_dir(), f"Expected workspace at {ws_path}"


class TestCrewList:
    async def test_list_empty(self, client):
        r = await client.get("/api/crews")
        assert r.status_code == 200
        assert r.json() == []

    async def test_list_multiple(self, client):
        await client.post("/api/crews", json={"name": "A"})
        await client.post("/api/crews", json={"name": "B"})
        await client.post("/api/crews", json={"name": "C"})
        r = await client.get("/api/crews")
        assert r.status_code == 200
        assert len(r.json()) == 3
        names = {c["name"] for c in r.json()}
        assert names == {"A", "B", "C"}


class TestCrewGet:
    async def test_get_existing(self, client):
        r = await client.post("/api/crews", json={"name": "GetMe"})
        crew_id = r.json()["id"]
        r = await client.get(f"/api/crews/{crew_id}")
        assert r.status_code == 200
        assert r.json()["name"] == "GetMe"

    async def test_get_nonexistent(self, client):
        r = await client.get("/api/crews/99999")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()


class TestCrewUpdate:
    async def test_update_name(self, client):
        r = await client.post("/api/crews", json={"name": "OldName"})
        crew_id = r.json()["id"]
        r = await client.put(f"/api/crews/{crew_id}", json={"name": "NewName"})
        assert r.status_code == 200
        assert r.json()["name"] == "NewName"

    async def test_update_workflow(self, client):
        r = await client.post("/api/crews", json={"name": "WF"})
        crew_id = r.json()["id"]
        r = await client.put(f"/api/crews/{crew_id}", json={
            "workflow_type": "roundtable",
            "workflow_config": {"max_rounds": 3}
        })
        assert r.status_code == 200
        assert r.json()["workflow_type"] == "roundtable"
        assert r.json()["workflow_config"]["max_rounds"] == 3

    async def test_update_nonexistent(self, client):
        r = await client.put("/api/crews/99999", json={"name": "X"})
        assert r.status_code == 404


class TestCrewDelete:
    async def test_delete_existing(self, client):
        r = await client.post("/api/crews", json={"name": "ToDelete"})
        crew_id = r.json()["id"]
        r = await client.delete(f"/api/crews/{crew_id}")
        assert r.status_code == 204
        # Verify gone
        r = await client.get(f"/api/crews/{crew_id}")
        assert r.status_code == 404

    async def test_delete_removes_workspace(self, client):
        r = await client.post("/api/crews", json={"name": "CleanWS"})
        data = r.json()
        ws_path = Path(f"test_workspace/{data['id']}_CleanWS")
        assert ws_path.is_dir()
        await client.delete(f"/api/crews/{data['id']}")
        assert not ws_path.exists(), f"Workspace should be removed: {ws_path}"

    async def test_delete_nonexistent(self, client):
        r = await client.delete("/api/crews/99999")
        assert r.status_code == 404
