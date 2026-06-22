"""Tests for workspace service: directory creation, isolation, and cleanup."""
import shutil
from pathlib import Path

from app.services.workspace import (
    init_agent_workspace,
    remove_agent_workspace,
    agent_dir,
    _sanitize,
)


class TestSanitize:
    def test_english_name(self):
        assert _sanitize("Hello") == "Hello"

    def test_chinese_name(self):
        assert _sanitize("测试团队") == "测试团队"

    def test_special_chars(self):
        assert _sanitize("hello world!") == "hello_world_"
        assert _sanitize("a/b:c") == "a_b_c"

    def test_long_name_truncated(self):
        long_name = "a" * 100
        assert len(_sanitize(long_name)) <= 64


class TestAgentWorkspace:
    def test_agent_dir_path(self):
        path = agent_dir(1, "AgentY", 3)
        assert "03_AgentY" in str(path)

    def test_init_creates_dir_and_readme(self):
        path = init_agent_workspace(200, "MyAgent", 0)
        assert path.is_dir()
        readme = path / "README.txt"
        assert readme.exists()
        content = readme.read_text(encoding="utf-8")
        assert "MyAgent" in content
        # Cleanup
        shutil.rmtree(path)

    def test_remove_agent_dir(self):
        path = init_agent_workspace(201, "DelAgent", 1)
        assert path.is_dir()
        remove_agent_workspace(201, "DelAgent", 1)
        assert not path.exists()

    def test_remove_nonexistent_agent_no_error(self):
        remove_agent_workspace(99999, "Y", 0)


class TestWorkspaceIsolation:
    def test_agents_have_different_dirs(self):
        path_a = init_agent_workspace(300, "AgentA", 0)
        path_b = init_agent_workspace(301, "AgentB", 1)
        assert path_a != path_b
        shutil.rmtree(path_a)
        shutil.rmtree(path_b)
