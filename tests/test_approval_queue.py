"""审批队列测试 — 覆盖添加、查询、审批、拒绝、并发安全。

依赖 Phase 0 修复的 threading.Lock 保障并发正确性。
"""

import concurrent.futures

from app.gateway.api.approvals import (
    add_approval, get_pending, resolve_approval,
    get_queue_size, clear_queue,
)


# ── 基本操作 ────────────────────────────────────────────────────────────


class TestBasicOperations:

    def test_add_approval_returns_id(self, clear_approvals):
        rid = add_approval("agent-a", "s1", "shell_exec", "rm -rf /tmp/x", "write")
        assert rid.startswith("approval_")
        assert len(rid) > len("approval_")

    def test_add_approval_increments_queue(self, clear_approvals):
        assert get_queue_size() == 0
        add_approval("a", "s1", "t", "x", "write")
        assert get_queue_size() == 1
        add_approval("a", "s2", "t", "y", "write")
        assert get_queue_size() == 2

    def test_pending_contains_all_fields(self, clear_approvals):
        rid = add_approval("agent-a", "session-1", "shell_exec", "rm -rf /tmp/x", "dangerous")
        pending = get_pending()
        assert len(pending) == 1
        item = pending[0]
        assert item["request_id"] == rid
        assert item["agent"] == "agent-a"
        assert item["session_id"] == "session-1"
        assert item["tool"] == "shell_exec"
        assert item["action"] == "rm -rf /tmp/x"
        assert item["permission"] == "dangerous"
        assert item["timestamp"]  # ISO 格式非空


# ── Session 过滤 ────────────────────────────────────────────────────────


class TestSessionFilter:

    def test_filter_matching_session(self, clear_approvals):
        add_approval("a1", "s1", "t", "x", "safe")
        add_approval("a2", "s2", "t", "y", "safe")
        assert len(get_pending("s1")) == 1
        assert get_pending("s1")[0]["agent"] == "a1"

    def test_filter_non_matching_session(self, clear_approvals):
        add_approval("a1", "s1", "t", "x", "safe")
        assert len(get_pending("s99")) == 0

    def test_filter_none_returns_all(self, clear_approvals):
        add_approval("a1", "s1", "t", "x", "safe")
        add_approval("a2", "s2", "t", "y", "safe")
        assert len(get_pending(None)) == 2

    def test_filter_empty_string(self, clear_approvals):
        add_approval("a1", "s1", "t", "x", "safe")
        # 空字符串视为 falsy，返回全部
        assert len(get_pending("")) == 1


# ── 审批与拒绝 ──────────────────────────────────────────────────────────


class TestResolve:

    def test_approve_removes_from_queue(self, clear_approvals):
        rid = add_approval("a", "s", "t", "x", "write")
        result = resolve_approval(rid, "approved")
        assert result is not None
        assert result["decision"] == "approved"
        assert get_queue_size() == 0

    def test_deny_removes_from_queue(self, clear_approvals):
        rid = add_approval("a", "s", "t", "x", "write")
        result = resolve_approval(rid, "denied")
        assert result is not None
        assert result["decision"] == "denied"
        assert get_queue_size() == 0

    def test_resolve_nonexistent_returns_none(self, clear_approvals):
        assert resolve_approval("nonexistent-id", "approved") is None

    def test_double_resolve_second_returns_none(self, clear_approvals):
        """同一个 request_id 只能 resolve 一次。"""
        rid = add_approval("a", "s", "t", "x", "write")
        first = resolve_approval(rid, "approved")
        assert first is not None
        second = resolve_approval(rid, "denied")
        assert second is None

    def test_resolve_only_affects_target(self, clear_approvals):
        """resolve 一个请求不影响队列中其他请求。"""
        rid1 = add_approval("a1", "s1", "t", "x", "safe")
        rid2 = add_approval("a2", "s2", "t", "y", "safe")
        resolve_approval(rid1, "approved")
        assert get_queue_size() == 1
        assert get_pending()[0]["request_id"] == rid2


# ── Queue 管理 ──────────────────────────────────────────────────────────


class TestQueueManagement:

    def test_clear_queue(self, clear_approvals):
        add_approval("a", "s", "t", "x", "safe")
        add_approval("b", "s", "t", "y", "safe")
        clear_queue()
        assert get_queue_size() == 0

    def test_get_queue_size_empty(self, clear_approvals):
        assert get_queue_size() == 0

    def test_request_ids_are_unique(self, clear_approvals):
        """两个审批应有不同的 request_id。"""
        rid1 = add_approval("a", "s", "t", "x", "safe")
        rid2 = add_approval("b", "s", "t", "y", "safe")
        assert rid1 != rid2


# ── 并发安全 ────────────────────────────────────────────────────────────


class TestConcurrency:
    """验证 threading.Lock 在并发场景下的正确性。"""

    def test_concurrent_add_approvals(self, clear_approvals):
        """并发添加审批请求，队列计数应准确。"""
        def add_one(i):
            return add_approval(f"agent-{i}", f"session-{i}", "tool", f"action-{i}", "safe")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(add_one, i) for i in range(50)]
            results = [f.result() for f in futures]

        assert len(results) == 50
        assert get_queue_size() == 50
        # 所有 request_id 唯一
        assert len(set(results)) == 50

    def test_concurrent_resolve_same_request(self, clear_approvals):
        """并发 resolve 同一 request_id，只有一人胜出。"""
        rid = add_approval("agent", "session", "tool", "action", "dangerous")

        resolved = []

        def try_resolve():
            result = resolve_approval(rid, "approved")
            if result is not None:
                resolved.append(True)
            return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(try_resolve) for _ in range(10)]
            for f in futures:
                f.result()

        # 只有一个人能 resolve 成功
        assert len(resolved) == 1
        assert get_queue_size() == 0

    def test_concurrent_add_and_get(self, clear_approvals):
        """并发添加和查询，不会丢失数据。"""
        def adder():
            for i in range(20):
                add_approval(f"agent-{i}", "s", "tool", "action", "safe")

        def reader(results_holder):
            for _ in range(5):
                pending = get_pending()
                results_holder.append(len(pending))

        sizes = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(adder) for _ in range(3)]
            futures += [executor.submit(reader, sizes) for _ in range(2)]
            for f in futures:
                f.result()

        # 最终应有 60 条（3×20）
        assert get_queue_size() == 60
