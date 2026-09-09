"""ticker 归一化纯逻辑单测（离线，无网络）。

断言基准为模块 docstring 声明 + 实测行为，覆盖四市场 canonical 形态、
前后缀剥离、类股分节、非法输入两条路径（抛错 / 返回 None）。
"""

from __future__ import annotations

import pytest

from download_financial_report.fins.ticker_normalization import (
    NormalizedTicker,
    normalize_ticker,
    try_normalize_ticker,
)


# ---- 港股：4 位补零 / 保留 5 位 ----

@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("0700", "0700"),
        ("700", "0700"),  # 自动补零
        ("00700", "0700"),
        ("00700.HK", "0700"),  # 后缀剥离
        ("HK.00700", "0700"),
        ("hk:700", "0700"),  # 大小写 + 冒号分隔
        ("9988", "9988"),
        ("89988", "89988"),  # 5 位保留
        ("1", "0001"),
    ],
)
def test_hk_canonical(raw: str, canonical: str) -> None:
    got = normalize_ticker(raw)
    assert got.market == "HK"
    assert got.exchange == "HKEX"
    assert got.canonical == canonical


# ---- A 股：沪 6 位（6 开头）/ 深 6 位（0、3 开头）----

@pytest.mark.parametrize(
    ("raw", "canonical", "exchange"),
    [
        ("600519", "600519", "SSE"),
        ("SH600519", "600519", "SSE"),  # 前缀无分隔
        ("sh:600519", "600519", "SSE"),
        ("688981", "688981", "SSE"),  # 科创板
        ("000333", "000333", "SZSE"),
        ("SZ.000333", "000333", "SZSE"),
        ("300750", "300750", "SZSE"),  # 创业板
    ],
)
def test_cn_canonical(raw: str, canonical: str, exchange: str) -> None:
    got = normalize_ticker(raw)
    assert got.market == "CN"
    assert got.exchange == exchange
    assert got.canonical == canonical


# ---- 美股：保留字母，点号/横杠类股统一为横杠 ----

@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("AAPL", "AAPL"),
        ("aapl", "AAPL"),  # 大写归一
        ("BRK-B", "BRK-B"),
        ("BRK.B", "BRK-B"),  # 类股分隔符统一
        ("brk.b", "BRK-B"),
        ("SHEL", "SHEL"),  # 防误剥 SH 前缀
    ],
)
def test_us_canonical(raw: str, canonical: str) -> None:
    got = normalize_ticker(raw)
    assert got.market == "US"
    assert got.exchange is None  # 无交易所后缀时不区分
    assert got.canonical == canonical


# ---- dataclass 字段 ----

def test_normalized_ticker_fields() -> None:
    got = normalize_ticker("hk:700")
    assert isinstance(got, NormalizedTicker)
    assert got.raw == "hk:700"  # raw 保留原始输入


# ---- 非法输入：抛错 / None 双路径 ----

@pytest.mark.parametrize("bad", ["", "ABC123XYZ", "60051X", "HK."])
def test_normalize_ticker_raises(bad: str) -> None:
    with pytest.raises(ValueError):
        normalize_ticker(bad)


def test_normalize_ticker_empty_message() -> None:
    with pytest.raises(ValueError, match="不能为空"):
        normalize_ticker("")


@pytest.mark.parametrize("bad", ["", "ABC123XYZ", "60051X", "HK."])
def test_try_normalize_ticker_returns_none(bad: str) -> None:
    assert try_normalize_ticker(bad) is None
