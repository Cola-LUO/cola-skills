"""CLI 冒烟测试（离线，不触网）。

只验证入口可执行、参数解析可用，不发任何网络请求：
argparse 在 ``_build_parser()`` 中只做声明，``--help`` 不会触发下载。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_BIN_DIR = Path(__file__).resolve().parents[1] / "bin"
COLA_FETCH = _BIN_DIR / "cola_fetch.py"
READ_HTM = _BIN_DIR / "read_htm.py"


def _run_cli(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


@pytest.mark.parametrize("script", [COLA_FETCH, READ_HTM])
def test_help_exits_zero(script: Path) -> None:
    """两个 CLI 入口的 --help 均应成功退出（语法 / import 链 OK）。"""
    proc = _run_cli(script, "--help")
    assert proc.returncode == 0, proc.stderr
    assert "usage" in proc.stdout.lower()


def test_cola_fetch_exposes_download_subcommand() -> None:
    proc = _run_cli(COLA_FETCH, "--help")
    assert "download" in proc.stdout


def test_all_package_modules_importable() -> None:
    """整包 import 冒烟：确保无残缺 import / 顶层语法错误。

    仅 import 模块（含 httpx/lxml/pymupdf 依赖解析），不执行任何网络调用。
    """
    import importlib

    modules = [
        "download_financial_report.log",
        "download_financial_report.workspace_paths",
        "download_financial_report.contracts.env_keys",
        "download_financial_report.fins.ticker_normalization",
        "download_financial_report.fins.domain.document_models",
        "download_financial_report.fins.downloaders.sec_downloader",
        "download_financial_report.fins.downloaders.hkexnews_downloader",
        "download_financial_report.fins.downloaders.cninfo_downloader",
    ]
    for mod in modules:
        importlib.import_module(mod)
