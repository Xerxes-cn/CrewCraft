"""人机交互队列测试 — 覆盖 confirm/select/input + 并发安全。"""

import concurrent.futures

from app.gateway.api.approvals import (
    add_interaction, get_pending, resolve_interaction, get_queue_size, clear_queue,
)


# ── 基本操作 ──────────────────────────────────────────────────────────


class TestBasicOperations:

    def test_add_interaction_returns_id(self, clear_approvals):
        rid = add_interaction("agent-a", "s1", "confirm", prompt="Proceed?")
        assert rid.startswith("itx_")

    def test_add_increments_queue(self, clear_approvals):
        assert get_queue_size() == 0
        add_interaction("a", "s1", "confirm")
        assert get_queue_size() == 1

    def test_select_with_options(self, clear_approvals):
        _ = add_interaction("a", "s1", "select", prompt="Pick", options=["a", "b"])
        pending = get_pending()
        assert pending[0]["type"] == "select"
        assert pending[0]["options"] == ["a", "b"]

    def test_input_type(self, clear_approvals):
        _ = add_interaction("a", "s1", "input", prompt="Enter value:")
        assert get_pending()[0]["type"] == "input"

    def test_pending_contains_all_fields(self, clear_approvals):
        add_interaction("agent-a", "s1", "confirm", prompt="Dangerous?",
                        options=[], metadata={"tool": "rm", "permission": "dangerous"})
        item = get_pending()[0]
        assert item["agent"] == "agent-a"
        assert item["type"] == "confirm"
        assert item["prompt"] == "Dangerous?"
        assert item["metadata"]["tool"] == "rm"

    def test_request_ids_unique(self, clear_approvals):
        r1 = add_interaction("a", "s", "confirm")
        r2 = add_interaction("b", "s", "confirm")
        assert r1 != r2


# ── Session 过滤 ──────────────────────────────────────────────────────


class TestSessionFilter:

    def test_filter_matching(self, clear_approvals):
        add_interaction("a1", "s1", "confirm")
        add_interaction("a2", "s2", "confirm")
        assert len(get_pending("s1")) == 1
        assert len(get_pending("s3")) == 0

    def test_none_returns_all(self, clear_approvals):
        add_interaction("a1", "s1", "confirm")
        add_interaction("a2", "s2", "confirm")
        assert len(get_pending(None)) == 2


# ── Resolve ───────────────────────────────────────────────────────────


class TestResolve:

    def test_resolve_confirm_approved(self, clear_approvals):
        rid = add_interaction("a", "s", "confirm", prompt="OK?")
        result = resolve_interaction(rid, "approved")
        assert result["response"] == "approved"
        assert get_queue_size() == 0

    def test_resolve_confirm_denied(self, clear_approvals):
        rid = add_interaction("a", "s", "confirm", prompt="OK?")
        result = resolve_interaction(rid, "denied")
        assert result["response"] == "denied"

    def test_resolve_select(self, clear_approvals):
        rid = add_interaction("a", "s", "select", prompt="Pick", options=["a", "b"])
        result = resolve_interaction(rid, "a")
        assert result["response"] == "a"

    def test_resolve_input(self, clear_approvals):
        rid = add_interaction("a", "s", "input", prompt="Enter:")
        result = resolve_interaction(rid, "hello world")
        assert result["response"] == "hello world"

    def test_resolve_nonexistent(self, clear_approvals):
        assert resolve_interaction("nonexistent", "x") is None

    def test_double_resolve_second_none(self, clear_approvals):
        rid = add_interaction("a", "s", "confirm")
        assert resolve_interaction(rid, "approved") is not None
        assert resolve_interaction(rid, "denied") is None

    def test_clear_queue(self, clear_approvals):
        add_interaction("a", "s", "confirm")
        add_interaction("b", "s", "confirm")
        clear_queue()
        assert get_queue_size() == 0


# ── 并发安全 ──────────────────────────────────────────────────────────


class TestConcurrency:

    def test_concurrent_add(self, clear_approvals):
        def add_one(i):
            return add_interaction(f"agent-{i}", f"s-{i}", "confirm")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(add_one, i) for i in range(50)]
            results = [f.result() for f in futures]

        assert len(results) == 50
        assert get_queue_size() == 50
        assert len(set(results)) == 50

    def test_concurrent_resolve_same(self, clear_approvals):
        rid = add_interaction("a", "s", "confirm")
        resolved = []

        def try_resolve():
            r = resolve_interaction(rid, "approved")
            if r is not None:
                resolved.append(True)

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
