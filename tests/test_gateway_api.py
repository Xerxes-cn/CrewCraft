"""Gateway REST API 集成测试 — 使用不含 lifespan 的测试用 FastAPI app。

避免 WebSocket 服务器启动、Channel 连接等副作用。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


# ── 测试用 FastAPI app（不含 lifespan，无副作用）──────────────────────────


def _build_test_app(agent_manager_instance):
    """构建仅含路由的 FastAPI 测试实例，不启动 WebSocket/Channel。"""
    from app.gateway.api.agents import router as agents_router
    from app.gateway.api.tasks import router as tasks_router
    from app.gateway.api.tools import router as tools_router
    from app.gateway.api.approvals import router as interactions_router
    from app.gateway.manager.ws_manager import ws_manager as _ws

    test_app = FastAPI()
    test_app.include_router(agents_router)
    test_app.include_router(tasks_router)
    test_app.include_router(tools_router)
    test_app.include_router(interactions_router)

    @test_app.get("/api/health")
    async def health():
        return {"status": "ok", "active_agents": _ws.active_agents}

    return test_app


# ── Fixture ─────────────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path):
    """每个测试独立的 TestClient，使用独立的 AgentManager 和临时目录。"""
    from app.gateway.manager.agent_manager import AgentManager

    data_dir = tmp_path / "data"
    fresh_mgr = AgentManager(data_dir=data_dir)

    with patch("app.gateway.api.agents.agent_manager", fresh_mgr), \
         patch("app.agent.prompt_generator.generate_prompt",
               return_value="You are a helpful assistant."), \
         patch("app.agent.prompt_generator.save_prompt", MagicMock()):
        test_app = _build_test_app(fresh_mgr)
        with TestClient(test_app) as tc:
            yield tc


# ── Health ──────────────────────────────────────────────────────────────


class TestHealth:
    """GET /api/health"""

    def test_health_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "active_agents" in data


# ── Agent CRUD ──────────────────────────────────────────────────────────


class TestAgentCreate:
    """POST /api/agents"""

    def test_create_agent_201(self, client):
        resp = client.post("/api/agents", json={
            "name": "dev", "model": "gpt-4o", "description": "Developer",
            "provider": "subprocess",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "dev"
        assert data["model"] == "gpt-4o"

    def test_create_duplicate_409(self, client):
        client.post("/api/agents", json={"name": "dev", "model": "gpt-4o"})
        resp = client.post("/api/agents", json={"name": "dev", "model": "gpt-4o"})
        assert resp.status_code == 409

    def test_create_with_minimal_fields(self, client):
        resp = client.post("/api/agents", json={"name": "minimal", "model": "gpt-4o"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "minimal"
        assert data["description"] == ""

    def test_create_with_provider(self, client):
        resp = client.post("/api/agents", json={
            "name": "docker-agent", "model": "claude", "provider": "docker"
        })
        assert resp.status_code == 201
        assert resp.json()["provider"] == "docker"


class TestAgentList:
    """GET /api/agents"""

    def test_list_empty(self, client):
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_multiple(self, client):
        client.post("/api/agents", json={"name": "a", "model": "gpt"})
        client.post("/api/agents", json={"name": "b", "model": "claude"})
        resp = client.get("/api/agents")
        data = resp.json()
        assert len(data) == 2
        names = {a["name"] for a in data}
        assert names == {"a", "b"}


class TestAgentGet:
    """GET /api/agents/{name}"""

    def test_get_existing(self, client):
        client.post("/api/agents", json={"name": "dev", "model": "gpt-4o", "description": "Dev"})
        resp = client.get("/api/agents/dev")
        assert resp.status_code == 200
        assert resp.json()["name"] == "dev"
        assert resp.json()["description"] == "Dev"

    def test_get_nonexistent_404(self, client):
        resp = client.get("/api/agents/nonexistent")
        assert resp.status_code == 404


class TestAgentDelete:
    """DELETE /api/agents/{name}"""

    def test_delete_existing(self, client):
        client.post("/api/agents", json={"name": "tmp", "model": "gpt"})
        resp = client.delete("/api/agents/tmp")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == "tmp"

    def test_delete_nonexistent_404(self, client):
        resp = client.delete("/api/agents/nonexistent")
        assert resp.status_code == 404


# ── Interactions API (new) ────────────────────────────────────────────────


class TestInteractionsAPI:

    @pytest.fixture
    def clear(self):
        from app.gateway.api.approvals import clear_queue
        clear_queue()
        yield
        clear_queue()

    def test_submit_confirm(self, client, clear):
        resp = client.post("/api/interactions/submit", json={
            "agent": "dev", "session_id": "s1",
            "type": "confirm", "prompt": "Run dangerous command?",
        })
        assert resp.status_code == 201
        assert resp.json()["request_id"].startswith("itx_")

    def test_submit_select(self, client, clear):
        resp = client.post("/api/interactions/submit", json={
            "agent": "dev", "session_id": "s1",
            "type": "select", "prompt": "Which environment?",
            "options": ["staging", "production"],
        })
        assert resp.status_code == 201

    def test_submit_input(self, client, clear):
        resp = client.post("/api/interactions/submit", json={
            "agent": "dev", "session_id": "s1",
            "type": "input", "prompt": "Enter API key:",
        })
        assert resp.status_code == 201

    def test_resolve(self, client, clear):
        submit = client.post("/api/interactions/submit", json={
            "agent": "a", "session_id": "s", "type": "confirm", "prompt": "OK?",
        })
        rid = submit.json()["request_id"]
        resp = client.post(f"/api/interactions/{rid}/resolve", json={"response": "approved"})
        assert resp.status_code == 200
        assert resp.json()["response"] == "approved"

    def test_resolve_select(self, client, clear):
        submit = client.post("/api/interactions/submit", json={
            "agent": "a", "session_id": "s", "type": "select",
            "prompt": "Pick", "options": ["a", "b"],
        })
        rid = submit.json()["request_id"]
        resp = client.post(f"/api/interactions/{rid}/resolve", json={"response": "a"})
        assert resp.json()["response"] == "a"

    def test_resolve_nonexistent_404(self, client, clear):
        resp = client.post("/api/interactions/fake-id/resolve", json={"response": "x"})
        assert resp.status_code == 404


