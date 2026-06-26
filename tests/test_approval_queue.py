"""人机交互队列测试 — 覆盖 confirm/select/input + 并发安全。"""

import concurrent.futures

from app.gateway.api.approvals import (
    add_interaction, add_approval,
    get_pending, resolve_interaction, resolve_approval,
    get_queue_size, clear_queue,
)


# ── 新 API: add_interaction ───────────────────────────────────────────


class TestInteractionAPI:

    def test_add_confirm_returns_id(self, clear_approvals):
        rid = add_interaction("agent-a", "s1", "confirm",
                              prompt="Delete file /tmp/x?", metadata={"tool": "rm"})
        assert rid.startswith("hq_")

    def test_add_select_with_options(self, clear_approvals):
        _ = add_interaction("agent-a", "s1", "select",
                            prompt="Which environment?", options=["staging", "prod"])
        pending = get_pending()
        assert pending[0]["type"] == "select"
        assert pending[0]["options"] == ["staging", "prod"]

    def test_add_input_type(self, clear_approvals):
        _ = add_interaction("agent-a", "s1", "input",
                            prompt="API key required:")
        pending = get_pending()
        assert pending[0]["type"] == "input"
        assert pending[0]["prompt"] == "API key required:"

    def test_resolve_confirm(self, clear_approvals):
        rid = add_interaction("a", "s", "confirm", prompt="Proceed?")
        result = resolve_interaction(rid, "approved")
        assert result is not None
        assert result["response"] == "approved"
        assert get_queue_size() == 0

    def test_resolve_select(self, clear_approvals):
        rid = add_interaction("a", "s", "select", prompt="Pick one", options=["a", "b"])
        result = resolve_interaction(rid, "a")
        assert result["response"] == "a"

    def test_resolve_input(self, clear_approvals):
        rid = add_interaction("a", "s", "input", prompt="Enter value:")
        result = resolve_interaction(rid, "my-input-value")
        assert result["response"] == "my-input-value"


# ── 向后兼容: add_approval / resolve_approval ─────────────────────────


class TestLegacyAPI:

    def test_add_approval_returns_id(self, clear_approvals):
        rid = add_approval("agent-a", "s1", "shell_exec", "rm -rf /tmp/x", "write")
        assert rid.startswith("hq_")

    def test_add_approval_increments_queue(self, clear_approvals):
        assert get_queue_size() == 0
        add_approval("a", "s1", "t", "x", "write")
        assert get_queue_size() == 1

    def test_pending_contains_prompt(self, clear_approvals):
        add_approval("agent-a", "session-1", "shell_exec", "rm -rf /tmp/x", "dangerous")
        pending = get_pending()
        item = pending[0]
        assert item["type"] == "confirm"
        assert item["agent"] == "agent-a"
        assert "prompt" in item

    def test_resolve_with_approved(self, clear_approvals):
        rid = add_approval("a", "s", "t", "x", "write")
        result = resolve_approval(rid, "approved")
        assert result is not None
        assert result["response"] == "approved"

    def test_resolve_with_denied(self, clear_approvals):
        rid = add_approval("a", "s", "t", "x", "write")
        result = resolve_approval(rid, "denied")
        assert result["response"] == "denied"


# ── Session 过滤 ──────────────────────────────────────────────────────


class TestSessionFilter:

    def test_filter_matching(self, clear_approvals):
        add_interaction("a1", "s1", "confirm", prompt="x")
        add_interaction("a2", "s2", "confirm", prompt="y")
        assert len(get_pending("s1")) == 1
        assert len(get_pending("s3")) == 0

    def test_filter_none_returns_all(self, clear_approvals):
        add_interaction("a1", "s1", "confirm")
        add_interaction("a2", "s2", "confirm")
        assert len(get_pending(None)) == 2


# ── 通用操作 ──────────────────────────────────────────────────────────


class TestCommon:

    def test_resolve_nonexistent_returns_none(self, clear_approvals):
        assert resolve_interaction("nonexistent", "x") is None

    def test_double_resolve_second_returns_none(self, clear_approvals):
        rid = add_interaction("a", "s", "confirm")
        assert resolve_interaction(rid, "approved") is not None
        assert resolve_interaction(rid, "denied") is None

    def test_clear_queue(self, clear_approvals):
        add_interaction("a", "s", "confirm")
        add_interaction("b", "s", "confirm")
        clear_queue()
        assert get_queue_size() == 0

    def test_get_queue_size_empty(self, clear_approvals):
        assert get_queue_size() == 0

    def test_request_ids_unique(self, clear_approvals):
        r1 = add_interaction("a", "s", "confirm")
        r2 = add_interaction("b", "s", "confirm")
        assert r1 != r2


# ── 并发安全 ──────────────────────────────────────────────────────────


class TestConcurrency:

    def test_concurrent_add(self, clear_approvals):
        def add_one(i):
            return add_interaction(f"agent-{i}", f"session-{i}", "confirm")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(add_one, i) for i in range(50)]
            results = [f.result() for f in futures]

        assert len(results) == 50
        assert get_queue_size() == 50
        assert len(set(results)) == 50

    def test_concurrent_resolve_same_request(self, clear_approvals):
        rid = add_interaction("agent", "session", "confirm")
        resolved = []

        def try_resolve():
            result = resolve_interaction(rid, "approved")
            if result is not None:
                resolved.append(True)
            return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(try_resolve) for _ in range(10)]
            for f in futures:
                f.result()

        assert len(resolved) == 1
        assert get_queue_size() == 0

    def test_concurrent_add_and_get(self, clear_approvals):
        def adder():
            for i in range(20):
                add_interaction(f"agent-{i}", "s", "confirm")

        sizes = []
        def reader():
            for _ in range(5):
                sizes.append(len(get_pending()))

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(adder) for _ in range(3)]
            futures += [executor.submit(reader) for _ in range(2)]
            for f in futures:
                f.result()

        assert get_queue_size() == 60
