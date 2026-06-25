"""Config 模块测试 — 覆盖所有 15 个配置字段。

使用 monkeypatch 严格隔离环境变量，断言失败不会泄漏。
"""

import pytest


# ── 辅助 ────────────────────────────────────────────────────────────────


def make_config(monkeypatch, overrides: dict | None = None):
    """用 monkeypatch 注入环境变量后创建 Config 实例。

    每个测试独立创建实例，不使用模块级单例 — 避免测试间耦合。
    """
    from app.config import Config

    defaults = {
        "CREWCRAFT_DATA_DIR": "/tmp/test-data",
        "CREWCRAFT_GATEWAY_HOST": "0.0.0.0",
        "CREWCRAFT_GATEWAY_PORT": "8080",
        "CREWCRAFT_WS_HOST": "0.0.0.0",
        "CREWCRAFT_WS_PORT": "9000",
        "CREWCRAFT_AGENT_DEPLOY_MODE": "docker",
        "CREWCRAFT_AGENT_PORT_START": "9100",
        "CREWCRAFT_AGENT_IDLE_TIMEOUT": "600",
        "CREWCRAFT_AGENT_HEARTBEAT_INTERVAL": "30",
        "CREWCRAFT_COLLAB_MAX_ROUNDS": "20",
        "CREWCRAFT_COLLAB_MAX_DEPTH": "5",
        "CREWCRAFT_COLLAB_TIMEOUT": "120",
        "CREWCRAFT_LOG_LEVEL": "DEBUG",
    }
    # Clear existing env vars first to avoid interference
    for key in defaults:
        monkeypatch.delenv(key, raising=False)

    merged = {**defaults, **(overrides or {})}
    for k, v in merged.items():
        monkeypatch.setenv(k, v)

    return Config()


# ── 逐字段验证 ──────────────────────────────────────────────────────────


class TestAllFields:
    """覆盖 Config 中每个字段的读取。"""

    def test_data_dir(self, monkeypatch):
        c = make_config(monkeypatch)
        assert c.data_dir.name == "test-data"

    def test_gateway_host(self, monkeypatch):
        c = make_config(monkeypatch, {"CREWCRAFT_GATEWAY_HOST": "10.0.0.1"})
        assert c.gateway_host == "10.0.0.1"

    def test_gateway_port(self, monkeypatch):
        c = make_config(monkeypatch, {"CREWCRAFT_GATEWAY_PORT": "9999"})
        assert c.gateway_port == 9999

    def test_ws_host(self, monkeypatch):
        c = make_config(monkeypatch, {"CREWCRAFT_WS_HOST": "10.0.0.2"})
        assert c.ws_host == "10.0.0.2"

    def test_ws_port(self, monkeypatch):
        c = make_config(monkeypatch, {"CREWCRAFT_WS_PORT": "8888"})
        assert c.ws_port == 8888

    def test_ws_url_composition(self, monkeypatch):
        """ws_url 由 ws_host + ws_port 拼接。"""
        c = make_config(monkeypatch, {
            "CREWCRAFT_WS_HOST": "gateway.local",
            "CREWCRAFT_WS_PORT": "7777",
        })
        assert c.ws_url == "ws://gateway.local:7777"

    def test_agent_deploy_mode(self, monkeypatch):
        c = make_config(monkeypatch, {"CREWCRAFT_AGENT_DEPLOY_MODE": "subprocess"})
        assert c.agent_deploy_mode == "subprocess"

    def test_agent_port_start(self, monkeypatch):
        c = make_config(monkeypatch, {"CREWCRAFT_AGENT_PORT_START": "9500"})
        assert c.agent_port_start == 9500

    def test_agent_idle_timeout(self, monkeypatch):
        c = make_config(monkeypatch, {"CREWCRAFT_AGENT_IDLE_TIMEOUT": "120"})
        assert c.agent_idle_timeout == 120

    def test_agent_heartbeat_interval(self, monkeypatch):
        c = make_config(monkeypatch, {"CREWCRAFT_AGENT_HEARTBEAT_INTERVAL": "10"})
        assert c.agent_heartbeat_interval == 10

    def test_collab_max_rounds(self, monkeypatch):
        c = make_config(monkeypatch, {"CREWCRAFT_COLLAB_MAX_ROUNDS": "50"})
        assert c.collab_max_rounds == 50

    def test_collab_max_depth(self, monkeypatch):
        c = make_config(monkeypatch, {"CREWCRAFT_COLLAB_MAX_DEPTH": "8"})
        assert c.collab_max_depth == 8

    def test_collab_timeout(self, monkeypatch):
        c = make_config(monkeypatch, {"CREWCRAFT_COLLAB_TIMEOUT": "90"})
        assert c.collab_timeout == 90

    def test_log_level(self, monkeypatch):
        c = make_config(monkeypatch, {"CREWCRAFT_LOG_LEVEL": "WARNING"})
        assert c.log_level == "WARNING"


# ── 默认值 ──────────────────────────────────────────────────────────────


class TestDefaults:
    """不设环境变量时的 fallback 默认值。"""

    def _clean_config(self, monkeypatch):
        """创建无任何环境变量的 Config。"""
        from app.config import Config

        all_keys = [
            "CREWCRAFT_DATA_DIR", "CREWCRAFT_GATEWAY_HOST", "CREWCRAFT_GATEWAY_PORT",
            "CREWCRAFT_WS_HOST", "CREWCRAFT_WS_PORT", "CREWCRAFT_AGENT_DEPLOY_MODE",
            "CREWCRAFT_AGENT_PORT_START", "CREWCRAFT_AGENT_IDLE_TIMEOUT",
            "CREWCRAFT_AGENT_HEARTBEAT_INTERVAL", "CREWCRAFT_COLLAB_MAX_ROUNDS",
            "CREWCRAFT_COLLAB_MAX_DEPTH", "CREWCRAFT_COLLAB_TIMEOUT",
            "CREWCRAFT_LOG_LEVEL",
        ]
        for key in all_keys:
            monkeypatch.delenv(key, raising=False)
        return Config()

    def test_default_gateway_host(self, monkeypatch):
        c = self._clean_config(monkeypatch)
        assert c.gateway_host == "127.0.0.1"

    def test_default_gateway_port(self, monkeypatch):
        c = self._clean_config(monkeypatch)
        assert c.gateway_port == 8000

    def test_default_ws_port(self, monkeypatch):
        c = self._clean_config(monkeypatch)
        assert c.ws_port == 8765

    def test_default_agent_port_start(self, monkeypatch):
        c = self._clean_config(monkeypatch)
        assert c.agent_port_start == 9001

    def test_default_log_level(self, monkeypatch):
        c = self._clean_config(monkeypatch)
        assert c.log_level == "INFO"

    def test_default_data_dir(self, monkeypatch):
        c = self._clean_config(monkeypatch)
        assert c.data_dir.name == "data"

    def test_default_deploy_mode(self, monkeypatch):
        c = self._clean_config(monkeypatch)
        assert c.agent_deploy_mode == "subprocess"

    def test_default_idle_timeout(self, monkeypatch):
        c = self._clean_config(monkeypatch)
        assert c.agent_idle_timeout == 300

    def test_default_heartbeat(self, monkeypatch):
        c = self._clean_config(monkeypatch)
        assert c.agent_heartbeat_interval == 15


# ── 边界与错误处理 ─────────────────────────────────────────────────────


class TestEdgeCases:
    """边界条件和错误输入。"""

    def test_port_zero(self, monkeypatch):
        """端口为 0 是有效的 int。"""
        c = make_config(monkeypatch, {"CREWCRAFT_GATEWAY_PORT": "0"})
        assert c.gateway_port == 0

    def test_port_negative_parses_as_int(self, monkeypatch):
        """负数端口 — int() 会接受，Config 不做业务校验。"""
        c = make_config(monkeypatch, {"CREWCRAFT_GATEWAY_PORT": "-1"})
        assert c.gateway_port == -1

    def test_port_non_numeric_raises(self, monkeypatch):
        """非数字端口应抛 ValueError。"""
        from app.config import Config

        monkeypatch.setenv("CREWCRAFT_GATEWAY_PORT", "abc")
        with pytest.raises(ValueError):
            Config()

    def test_empty_data_dir(self, monkeypatch):
        """空 data_dir — Path('') 是合法的，name 为 ''。"""
        c = make_config(monkeypatch, {"CREWCRAFT_DATA_DIR": ""})
        assert c.data_dir.name == ""

    def test_very_large_port(self, monkeypatch):
        c = make_config(monkeypatch, {"CREWCRAFT_GATEWAY_PORT": "65535"})
        assert c.gateway_port == 65535

    def test_empty_log_level(self, monkeypatch):
        c = make_config(monkeypatch, {"CREWCRAFT_LOG_LEVEL": ""})
        assert c.log_level == ""


# ── 缓存行为（值不变性）─────────────────────────────────────────────────


class TestImmutability:
    """Config 实例创建后，修改环境变量不影响已缓存的属性。"""

    def test_cached_values_independent_of_env_change(self, monkeypatch):
        """验证单例实例的缓存不随后续 setenv 改变。"""
        from app.config import Config

        monkeypatch.setenv("CREWCRAFT_GATEWAY_PORT", "5555")
        c = Config()
        assert c.gateway_port == 5555

        # 修改环境变量
        monkeypatch.setenv("CREWCRAFT_GATEWAY_PORT", "6666")
        # 原实例值不变
        assert c.gateway_port == 5555

    def test_new_instance_reads_new_env(self, monkeypatch):
        """新实例读取最新环境变量。"""
        from app.config import Config

        monkeypatch.setenv("CREWCRAFT_GATEWAY_PORT", "1111")
        c1 = Config()
        assert c1.gateway_port == 1111

        monkeypatch.setenv("CREWCRAFT_GATEWAY_PORT", "2222")
        c2 = Config()
        assert c2.gateway_port == 2222
