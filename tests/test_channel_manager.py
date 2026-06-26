"""Channel 管理模块测试 — 注册、加载、启停。"""

import json
from unittest.mock import patch

from app.channels import register_channel_type, _CHANNEL_TYPES
from app.channels.base import BaseChannel


# ── 注册 ────────────────────────────────────────────────────────────────


class TestRegistration:

    def test_register_adds_to_registry(self):
        class TestCh(BaseChannel):
            name = "test-type"
            display_name = "Test"

            async def start(self): pass
            async def stop(self): pass
            async def send(self, msg): pass

        register_channel_type("test-type", TestCh)
        assert "test-type" in _CHANNEL_TYPES
        assert _CHANNEL_TYPES["test-type"] is TestCh

    def test_builtin_cli_registered(self):
        """CLI Channel 在导入 app.channels 时自动注册。"""
        assert "cli" in _CHANNEL_TYPES


# ── 配置加载 ───────────────────────────────────────────────────────────


class TestLoadInstances:

    def test_empty_config_dir_creates_default(self, tmp_path):
        """channels.json 不存在时创建默认配置并返回空列表。"""
        from app.channels import _load_channel_instances

        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True)

        with patch("app.channels.app_config") as mock_cfg:
            mock_cfg.data_dir = data_dir
            instances = _load_channel_instances()
            assert instances == []
            channels_file = data_dir / "channels.json"
            assert channels_file.exists()
            data = json.loads(channels_file.read_text())
            assert "channels" in data

    def test_disabled_channel_skipped(self, tmp_path):
        from app.channels import _load_channel_instances

        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "channels.json").write_text(json.dumps({
            "channels": [
                {"type": "cli", "name": "cli-1", "enabled": False},
                {"type": "cli", "name": "cli-2", "enabled": True},
            ]
        }))

        with patch("app.channels.app_config") as mock_cfg:
            mock_cfg.data_dir = data_dir
            instances = _load_channel_instances()
            names = {ch.config.get("name") for ch in instances}
            assert "cli-1" not in names
            assert "cli-2" in names

    def test_unknown_channel_type_skipped(self, tmp_path):
        from app.channels import _load_channel_instances

        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "channels.json").write_text(json.dumps({
            "channels": [
                {"type": "unknown_platform", "name": "test", "enabled": True},
                {"type": "cli", "name": "cli-1", "enabled": True},
            ]
        }))

        with patch("app.channels.app_config") as mock_cfg:
            mock_cfg.data_dir = data_dir
            instances = _load_channel_instances()
            assert len(instances) == 1
            assert instances[0].name == "cli"
