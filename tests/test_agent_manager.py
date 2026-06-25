"""AgentManager CRUD 与配置持久化测试。"""

import json
import pytest

from app.gateway.manager.agent_manager import AgentConfig, AgentManager


# ── 基本 CRUD ───────────────────────────────────────────────────────────


class TestSaveAndLoad:

    def test_save_and_load_roundtrip(self, agent_manager):
        cfg = AgentConfig(name="test", model="gpt", description="test desc")
        agent_manager.save_config(cfg)

        loaded = agent_manager.load_config("test")
        assert loaded is not None
        assert loaded.name == "test"
        assert loaded.model == "gpt"
        assert loaded.description == "test desc"

    def test_save_overwrites_existing(self, agent_manager):
        agent_manager.save_config(AgentConfig(name="dup", model="gpt"))
        agent_manager.save_config(AgentConfig(name="dup", model="claude"))
        loaded = agent_manager.load_config("dup")
        assert loaded.model == "claude"

    def test_load_nonexistent_returns_none(self, agent_manager):
        assert agent_manager.load_config("nonexistent") is None

    def test_new_directory_structure(self, agent_manager):
        agent_manager.save_config(AgentConfig(name="new", model="gpt"))
        assert (agent_manager.agents_dir / "new" / "config.json").exists()

    def test_save_persists_all_fields(self, agent_manager):
        cfg = AgentConfig(
            name="full", model="gpt-4", description="desc",
            provider="docker", port=9005, idle_timeout=120,
            created_at="2025-06-01T00:00:00Z",
        )
        agent_manager.save_config(cfg)
        loaded = agent_manager.load_config("full")
        assert loaded.name == "full"
        assert loaded.model == "gpt-4"
        assert loaded.description == "desc"
        assert loaded.provider == "docker"
        assert loaded.port == 9005
        assert loaded.idle_timeout == 120
        assert loaded.created_at == "2025-06-01T00:00:00Z"


# ── 列表与删除 ──────────────────────────────────────────────────────────


class TestListAndDelete:

    def test_list_configs_empty(self, agent_manager):
        assert agent_manager.list_configs() == []

    def test_list_configs_multiple(self, agent_manager):
        agent_manager.save_config(AgentConfig(name="a", model="gpt"))
        agent_manager.save_config(AgentConfig(name="b", model="claude"))
        configs = agent_manager.list_configs()
        names = {c.name for c in configs}
        assert names == {"a", "b"}

    def test_delete_existing(self, agent_manager):
        agent_manager.save_config(AgentConfig(name="x", model="gpt"))
        assert agent_manager.delete_config("x") is True
        assert agent_manager.load_config("x") is None

    def test_delete_nonexistent_returns_false(self, agent_manager):
        assert agent_manager.delete_config("nonexistent") is False

    def test_list_skips_invalid_json(self, agent_manager):
        """损坏的 config.json 应被跳过而非崩溃。"""
        d = agent_manager.agents_dir / "corrupt"
        d.mkdir(parents=True)
        (d / "config.json").write_text("not valid json{{")
        configs = agent_manager.list_configs()
        names = {c.name for c in configs}
        assert "corrupt" not in names

    def test_delete_old_format_file(self, agent_manager):
        """旧格式 data/agents/{name}.json 能被删除。"""
        old_file = agent_manager.agents_dir / "old.json"
        old_file.parent.mkdir(parents=True, exist_ok=True)
        old_file.write_text(json.dumps({"name": "old", "model": "gpt"}))
        assert agent_manager.delete_config("old") is True
        assert not old_file.exists()


# ── 端口分配 ────────────────────────────────────────────────────────────


class TestPortAllocation:

    def test_next_port_returns_start_when_empty(self, agent_manager, monkeypatch):
        monkeypatch.setenv("CREWCRAFT_AGENT_PORT_START", "9001")
        assert agent_manager.next_port() == 9001

    def test_next_port_skips_used(self, agent_manager, monkeypatch):
        monkeypatch.setenv("CREWCRAFT_AGENT_PORT_START", "9001")
        agent_manager.save_config(AgentConfig(name="a", model="gpt", port=9001))
        assert agent_manager.next_port() == 9002

    def test_next_port_fills_gap(self, agent_manager, monkeypatch):
        """已用端口 9001, 9003 → 应返回 9002。"""
        monkeypatch.setenv("CREWCRAFT_AGENT_PORT_START", "9001")
        agent_manager.save_config(AgentConfig(name="a", model="gpt", port=9001))
        agent_manager.save_config(AgentConfig(name="b", model="gpt", port=9003))
        assert agent_manager.next_port() == 9002

    def test_next_port_sequential(self, agent_manager, monkeypatch):
        """连续分配端口不重复。"""
        monkeypatch.setenv("CREWCRAFT_AGENT_PORT_START", "9001")
        seen = set()
        for i in range(5):
            port = agent_manager.next_port()
            assert port not in seen
            seen.add(port)
            agent_manager.save_config(AgentConfig(name=f"a{i}", model="gpt", port=port))
        assert len(seen) == 5


# ── 迁移 ────────────────────────────────────────────────────────────────


class TestMigration:

    def test_migrate_old_format(self, agent_manager):
        old = agent_manager.agents_dir / "old.json"
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_text(json.dumps({"name": "old", "model": "gpt", "description": "old"}))
        loaded = agent_manager.load_config("old")
        assert loaded is not None
        assert loaded.name == "old"
        # 迁移后新路径应存在
        assert (agent_manager.agents_dir / "old" / "config.json").exists()
        # 旧文件应已移走
        assert not old.exists()

    def test_migrate_skips_if_new_exists(self, agent_manager):
        """新旧格式同时存在时，直接读新的。"""
        old = agent_manager.agents_dir / "already.json"
        old.write_text(json.dumps({"name": "already", "model": "old-model"}))
        new_dir = agent_manager.agents_dir / "already"
        new_dir.mkdir(parents=True)
        (new_dir / "config.json").write_text(
            json.dumps({"name": "already", "model": "new-model"}))
        loaded = agent_manager.load_config("already")
        assert loaded.model == "new-model"


# ── AgentConfig 序列化 ──────────────────────────────────────────────────


class TestAgentConfigModel:

    def test_to_dict_contains_all_keys(self):
        cfg = AgentConfig(name="t", model="m", description="d", provider="p",
                          port=123, idle_timeout=60, created_at="t")
        d = cfg.to_dict()
        assert d["name"] == "t"
        assert d["model"] == "m"
        assert d["description"] == "d"
        assert d["provider"] == "p"
        assert d["port"] == 123
        assert d["idle_timeout"] == 60
        assert d["created_at"] == "t"

    def test_from_dict_with_all_fields(self):
        data = {"name": "x", "model": "y", "description": "z", "provider": "p",
                "port": 999, "idle_timeout": 30, "created_at": "2025"}
        cfg = AgentConfig.from_dict(data)
        assert cfg.name == "x"
        assert cfg.port == 999
        assert cfg.idle_timeout == 30

    def test_from_dict_minimal(self):
        """只给必填字段。"""
        cfg = AgentConfig.from_dict({"name": "min", "model": "gpt"})
        assert cfg.name == "min"
        assert cfg.model == "gpt"
        assert cfg.description == ""
        assert cfg.provider == ""
        assert cfg.port == 0
        assert cfg.idle_timeout == 300
        assert cfg.created_at == ""

    def test_from_dict_missing_name_raises(self):
        with pytest.raises(KeyError):
            AgentConfig.from_dict({"model": "gpt"})

    def test_from_dict_missing_model_raises(self):
        with pytest.raises(KeyError):
            AgentConfig.from_dict({"name": "x"})

    def test_from_dict_backcompat_system_prompt(self):
        """from_dict 用 system_prompt key 作为 description 的 fallback。"""
        cfg = AgentConfig.from_dict({"name": "x", "model": "gpt", "system_prompt": "old prompt"})
        assert cfg.description == "old prompt"

    def test_to_dict_from_dict_roundtrip(self):
        original = AgentConfig(name="r", model="m", description="d",
                               provider="p", port=42, idle_timeout=99, created_at="t")
        reconstructed = AgentConfig.from_dict(original.to_dict())
        assert reconstructed.name == original.name
        assert reconstructed.model == original.model
        assert reconstructed.description == original.description
        assert reconstructed.provider == original.provider
        assert reconstructed.port == original.port
        assert reconstructed.idle_timeout == original.idle_timeout
        assert reconstructed.created_at == original.created_at


# ── 在线状态 ────────────────────────────────────────────────────────────


class TestOnlineState:

    def test_is_online_defaults_false(self, agent_manager):
        assert agent_manager.is_online("any") is False

    def test_set_online_roundtrip(self, agent_manager):
        agent_manager.set_online("agent-1", True)
        assert agent_manager.is_online("agent-1") is True
        agent_manager.set_online("agent-1", False)
        assert agent_manager.is_online("agent-1") is False

    def test_start_agent_unknown_returns_none(self, agent_manager):
        """启动不存在的 Agent 返回 None。"""
        import asyncio
        result = asyncio.run(agent_manager.start_agent("nonexistent"))
        assert result is None

    def test_shutdown_all_no_agents(self, agent_manager):
        """无 Agent 时 shutdown 不抛异常。"""
        import asyncio
        asyncio.run(agent_manager.shutdown_all())
