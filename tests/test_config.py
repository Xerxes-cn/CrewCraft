"""Config 模块测试。"""

import os
import importlib
import app.config


def reload_config():
    """强制重新加载 Config 模块读取最新 env。"""
    importlib.reload(app.config)
    return app.config.config


def test_defaults():
    """测试默认值（无 env 覆盖）。"""
    old = os.environ.pop("CREWCRAFT_DATA_DIR", None)
    c = reload_config()
    assert c.gateway_host == "127.0.0.1"
    assert c.gateway_port == 8000
    assert c.ws_port == 8765
    assert c.agent_port_start == 9001
    assert c.log_level == "INFO"
    if old:
        os.environ["CREWCRAFT_DATA_DIR"] = old


def test_env_override():
    os.environ["CREWCRAFT_GATEWAY_PORT"] = "9999"
    c = reload_config()
    assert c.gateway_port == 9999
    del os.environ["CREWCRAFT_GATEWAY_PORT"]


def test_values_cached():
    c = reload_config()
    port1 = c.gateway_port
    os.environ["CREWCRAFT_GATEWAY_PORT"] = "8888"
    port2 = c.gateway_port
    assert port1 == port2
    del os.environ["CREWCRAFT_GATEWAY_PORT"]
