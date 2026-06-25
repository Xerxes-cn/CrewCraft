"""AgentManager CRUD 测试。"""

from app.gateway.manager.agent_manager import AgentConfig, AgentManager


def test_save_and_load(temp_data_dir):
    """测试保存和加载配置。"""
    mgr = AgentManager(data_dir=temp_data_dir)
    cfg = AgentConfig(name="test", model="gpt", description="test desc")
    mgr.save_config(cfg)

    loaded = mgr.load_config("test")
    assert loaded is not None
    assert loaded.name == "test"
    assert loaded.model == "gpt"
    assert loaded.description == "test desc"


def test_list_configs(temp_data_dir):
    """测试列出配置。"""
    mgr = AgentManager(data_dir=temp_data_dir)
    mgr.save_config(AgentConfig(name="a", model="gpt"))
    mgr.save_config(AgentConfig(name="b", model="claude"))

    configs = mgr.list_configs()
    assert len(configs) == 2
    names = {c.name for c in configs}
    assert names == {"a", "b"}


def test_delete_config(temp_data_dir):
    """测试删除配置。"""
    mgr = AgentManager(data_dir=temp_data_dir)
    mgr.save_config(AgentConfig(name="x", model="gpt"))
    assert mgr.load_config("x") is not None

    mgr.delete_config("x")
    assert mgr.load_config("x") is None


def test_not_found(temp_data_dir):
    """测试不存在的配置。"""
    mgr = AgentManager(data_dir=temp_data_dir)
    assert mgr.load_config("nonexistent") is None
    assert mgr.delete_config("nonexistent") is False


def test_duplicate(temp_data_dir):
    """测试重复保存（覆盖）。"""
    mgr = AgentManager(data_dir=temp_data_dir)
    cfg1 = AgentConfig(name="dup", model="gpt")
    cfg2 = AgentConfig(name="dup", model="claude")
    mgr.save_config(cfg1)
    mgr.save_config(cfg2)
    loaded = mgr.load_config("dup")
    assert loaded.model == "claude"


def test_port_allocation(temp_data_dir):
    """测试端口分配。"""
    mgr = AgentManager(data_dir=temp_data_dir)
    p1 = mgr.next_port()
    assert p1 >= 9001
    mgr.save_config(AgentConfig(name="a", model="gpt", port=p1))
    p2 = mgr.next_port()
    assert p2 > p1


def test_migration_old_format(temp_data_dir):
    """测试旧格式迁移。"""
    import json
    old = temp_data_dir / "agents" / "old.json"
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_text(json.dumps({"name": "old", "model": "gpt", "description": "old"}))
    mgr = AgentManager(data_dir=temp_data_dir)
    loaded = mgr.load_config("old")
    assert loaded is not None
    assert loaded.name == "old"
    assert (temp_data_dir / "agents" / "old" / "config.json").exists()


def test_new_directory_structure(temp_data_dir):
    """测试新目录结构。"""
    mgr = AgentManager(data_dir=temp_data_dir)
    mgr.save_config(AgentConfig(name="new", model="gpt"))
    assert (temp_data_dir / "agents" / "new" / "config.json").exists()
