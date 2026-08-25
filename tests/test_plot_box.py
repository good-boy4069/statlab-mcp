"""tests/test_plot_box.py —— 工具 25 测试。
独立性：五数概括与 describe 交叉核对；异常数与 outlier_detect 的 income 一致。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.visualization_plot_box import plot_box

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
FIX = ROOT / "tests" / "fixtures"


def test_clean_box_cross_check():
    r = plot_box(str(SAMPLES / "clean.csv"), column="score")
    assert r["status"] == "ok", r.get("message")
    rs = r["result"]
    assert rs["n"] == 50
    from statlab_mcp.tools.data_exploration_describe_statistics import (
        describe_statistics,
    )
    d = describe_statistics(str(SAMPLES / "clean.csv"))["result"]["columns"]["score"]
    assert rs["q1"] == pytest.approx(d["q1"])
    assert rs["median"] == pytest.approx(d["median"])
    assert rs["q3"] == pytest.approx(d["q3"])
    img = Path(r["__image__"])
    assert img.suffix == ".png" and img.exists()


def test_income_outlier_count_matches():
    """income 的 IQR 异常数应与 outlier_detect 一致（1 个）。"""
    r = plot_box(str(SAMPLES / "clean.csv"), column="income")
    assert r["result"]["n_outliers"] == 1
    from statlab_mcp.tools.data_exploration_outlier_detect import outlier_detect
    od = outlier_detect(str(SAMPLES / "clean.csv"))
    assert r["result"]["n_outliers"] == od["result"]["columns"]["income"]["n_outliers"]


def test_small_n_semantics():
    r = plot_box(str(FIX / "single_row.csv"), column="x")
    assert r["status"] == "ok"
    rs = r["result"]
    assert rs["q1"] is None and rs["lower_bound"] is None
    assert rs["n_outliers"] == 0
    assert "无法定义 IQR" in r["summary"]


def test_errors():
    assert "缺少必需列" in plot_box(str(SAMPLES / "clean.csv"),
                                     column="nope")["message"]
    assert "不是数值列" in plot_box(str(SAMPLES / "clean.csv"),
                                     column="category")["message"]
    assert plot_box(str(SAMPLES / "nope.csv"), column="x")["status"] == "error"


def test_json_safe():
    r = plot_box(str(SAMPLES / "clean.csv"), column="score")
    json.dumps(r, allow_nan=False, ensure_ascii=False)
