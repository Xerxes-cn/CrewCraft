"""审批队列测试。"""

import pytest
from app.gateway.api.approvals import (
    add_approval, get_pending, resolve_approval,
    get_queue_size, clear_queue,
)


@pytest.fixture(autouse=True)
def _clear():
    """每个测试前后清空队列。"""
    clear_queue()
    yield
    clear_queue()


def test_add_and_get():
    rid = add_approval("test-agent", "s1", "shell_exec", "rm -rf /tmp/x", "write")
    assert rid.startswith("approval_")
    assert get_queue_size() == 1
    pending = get_pending()
    assert pending[0]["agent"] == "test-agent"


def test_filter_by_session():
    add_approval("a1", "s1", "t1", "x", "write")
    add_approval("a2", "s2", "t2", "y", "write")
    assert len(get_pending("s1")) == 1
    assert len(get_pending("s2")) == 1
    assert len(get_pending("s3")) == 0


def test_approve():
    rid = add_approval("a", "s", "t", "x", "write")
    result = resolve_approval(rid, "approved")
    assert result is not None
    assert result["decision"] == "approved"
    assert get_queue_size() == 0


def test_deny():
    rid = add_approval("a", "s", "t", "x", "write")
    result = resolve_approval(rid, "denied")
    assert result["decision"] == "denied"
    assert get_queue_size() == 0


def test_not_found():
    assert resolve_approval("nonexistent", "approved") is None
