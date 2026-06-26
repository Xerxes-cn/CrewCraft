"""Channel 实现 smoke test — 验证每个 Channel 类可实例化、基本属性正确。

不调用 start()，不连接真实 IM 平台。
"""

class TestWeChatChannel:

    def test_instantiation(self):
        from app.channels.wechat import WeChatChannel
        ch = WeChatChannel({"name": "test", "token": "fake-token"})
        assert ch.name == "wechat"
        assert ch.display_name == "WeChat"
        assert ch.is_running is False

    def test_no_token_instantiation(self):
        from app.channels.wechat import WeChatChannel
        ch = WeChatChannel({"name": "test"})
        assert ch.name == "wechat"


class TestDingTalkChannel:

    def test_instantiation(self):
        """即使 SDK 不可用，类也应可实例化。"""
        from app.channels.dingtalk import DingTalkChannel
        ch = DingTalkChannel({"name": "test"})
        assert ch.name == "dingtalk"
        assert ch.display_name == "DingTalk"
        assert ch.is_running is False


class TestFeishuChannel:

    def test_instantiation(self):
        from app.channels.feishu import FeishuChannel
        ch = FeishuChannel({"name": "test"})
        assert ch.name == "feishu"
        assert ch.display_name == "Feishu"
        assert ch.is_running is False


class TestCLIChannel:

    def test_instantiation(self):
        from app.channels.cli import CLIChannel
        ch = CLIChannel({"name": "test-cli"})
        assert ch.name == "cli"
        assert ch.display_name == "CLI"
        assert ch.is_running is False
