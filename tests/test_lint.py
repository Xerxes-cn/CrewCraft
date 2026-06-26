"""Lint 检查 — 每次 pytest 运行时自动执行。

使用 pyflakes 检测所有源码文件中的未使用 import、未定义变量等问题。
"""

import subprocess
import sys
from pathlib import Path


# 故意的副作用导入 — pyflakes 会报告为 "imported but unused"，但实际通过 import 触发了注册
ALLOWED_UNUSED = {
    "app/agent/tools/__init__.py": [
        "'.web' imported but unused",
        "'.system' imported but unused",
        "'.utility' imported but unused",
        "'.collab' imported but unused",
    ],
    "app/channels/__init__.py": [
        "'.cli as _' imported but unused",
    ],
}


def get_package_root() -> Path:
    """返回项目根目录。"""
    return Path(__file__).resolve().parents[1]


def run_pyflakes() -> list[str]:
    """运行 pyflakes 并返回所有 warning 行。"""
    root = get_package_root()
    result = subprocess.run(
        [sys.executable, "-m", "pyflakes", str(root / "app"), str(root / "tests")],
        capture_output=True, text=True, timeout=30,
    )
    # pyflakes 把 warnings 输出到 stdout
    lines = result.stdout.strip().split("\n")
    return [ln for ln in lines if ln]  # 过滤空行


def is_allowed(line: str) -> bool:
    """判断该 warning 是否属于故意的副作用导入。"""
    for file, messages in ALLOWED_UNUSED.items():
        for msg in messages:
            if file in line and msg in line:
                return True
    return False


def test_no_pyflakes_errors():
    """除已知的副作用导入外，不应有其他 pyflakes 错误。"""
    warnings = run_pyflakes()

    unexpected = [w for w in warnings if not is_allowed(w)]

    if unexpected:
        msg = f"pyflakes found {len(unexpected)} unexpected issue(s):\n"
        msg += "\n".join(f"  {u}" for u in unexpected)
        msg += "\n\n💡 提示: 如果新增的是故意的副作用导入，请更新 tests/test_lint.py 中的 ALLOWED_UNUSED"
        raise AssertionError(msg)

    # 只允许已知的副作用导入，数量也核对
    expected_count = sum(len(msgs) for msgs in ALLOWED_UNUSED.values())
    assert len(warnings) == expected_count, (
        f"Expected {expected_count} allowed warnings, got {len(warnings)}\n"
        + "\n".join(f"  {w}" for w in warnings)
    )
