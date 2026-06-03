"""Tests for workspace service: directory creation, isolation, and cleanup."""
import shutil
from pathlib import Path

import pytest

from app.services.workspace import (
    init_crew_workspace,
    init_agent_workspace,
    remove_crew_workspace,
    remove_agent_workspace,
    crew_dir,
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


class TestCrewWorkspace:
    def test_crew_dir_path(self):
        path = crew_dir(42, "My Team")
        assert path.name.startswith("42_")
        assert "My_Team" in path.name

    def test_init_creates_dir(self):
        path = init_crew_workspace(100, "TestCrew")
        assert path.is_dir()
        # Cleanup
        shutil.rmtree(path)

    def test_init_idempotent(self):
        path = init_crew_workspace(101, "TestCrew2")
        path2 = init_crew_workspace(101, "TestCrew2")
        assert path == path2
        assert path.is_dir()
        shutil.rmtree(path)

    def test_remove_crew_dir(self):
        path = init_crew_workspace(102, "ToRemove")
        assert path.is_dir()
        remove_crew_workspace(102, "ToRemove")
        assert not path.exists()

    def test_remove_nonexistent_no_error(self):
        remove_crew_workspace(99999, "NoSuch")


class TestAgentWorkspace:
    def test_agent_dir_path(self):
        path = agent_dir(1, "CrewX", "AgentY", 3)
        assert "1_CrewX" in str(path)
        assert "03_AgentY" in str(path)

    def test_init_creates_dir_and_readme(self):
        init_crew_workspace(200, "ParentCrew")
        path = init_agent_workspace(200, "ParentCrew", "MyAgent", 0)
        assert path.is_dir()
        readme = path / "README.txt"
        assert readme.exists()
        content = readme.read_text(encoding="utf-8")
        assert "MyAgent" in content
        assert "ParentCrew" in content
        # Cleanup
        remove_crew_workspace(200, "ParentCrew")

    def test_remove_agent_dir(self):
        init_crew_workspace(201, "CrewDel")
        path = init_agent_workspace(201, "CrewDel", "DelAgent", 1)
        assert path.is_dir()
        remove_agent_workspace(201, "CrewDel", "DelAgent", 1)
        assert not path.exists()
        # Crew dir should still exist
        assert crew_dir(201, "CrewDel").is_dir()
        remove_crew_workspace(201, "CrewDel")

    def test_remove_nonexistent_agent_no_error(self):
        remove_agent_workspace(99999, "X", "Y", 0)


class TestWorkspaceIsolation:
    def test_agents_have_different_dirs(self):
        init_crew_workspace(300, "IsoCrew")
        path_a = init_agent_workspace(300, "IsoCrew", "AgentA", 0)
        path_b = init_agent_workspace(300, "IsoCrew", "AgentB", 1)
        assert path_a != path_b
        assert path_a.parent == path_b.parent  # same crew dir
        remove_crew_workspace(300, "IsoCrew")

    def test_crews_have_different_dirs(self):
        path_a = init_crew_workspace(400, "CrewA")
        path_b = init_crew_workspace(401, "CrewB")
        assert path_a != path_b
        remove_crew_workspace(400, "CrewA")
        remove_crew_workspace(401, "CrewB")
