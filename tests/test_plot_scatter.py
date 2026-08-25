"""tests/test_plot_scatter.py —— 工具 21 测试。
独立性：r 与 correlation_matrix 实测值交叉核对；图文件存在性断言。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.visualization_plot_scatter import plot_scatter

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def test_clean_scatter_r_cross_check():
    r = plot_scatter(str(SAMPLES / "clean.csv"), x_col="age", y_col="income")
    assert r["status"] == "ok", r.get("message")
    rs = r["result"]
    assert rs["n"] == 50 and rs["dropped_rows"] == 0
    from statlab_mcp.tools.data_exploration_correlation_matrix import (
        correlation_matrix,
    )
    cm = correlation_matrix(str(SAMPLES / "clean.csv"))["result"]["correlation"]
    assert rs["pearson_r"] == pytest.approx(cm["age"]["income"], abs=1e-12)
    img = Path(r["__image__"])
    assert img.is_absolute() and img.suffix == ".png" and img.exists()
    assert "相关≠因果" in r["summary"]


def test_errors():
    assert "缺少必需列" in plot_scatter(str(SAMPLES / "clean.csv"),
                                        x_col="nope", y_col="income")["message"]
    assert "不是数值列" in plot_scatter(str(SAMPLES / "clean.csv"),
                                        x_col="category", y_col="income")["message"]
    assert plot_scatter(str(SAMPLES / "nope.csv"), x_col="a",
                        y_col="b")["status"] == "error"


def test_constant_col_r_null(FIX=ROOT / "tests" / "fixtures"):
    r = plot_scatter(str(FIX / "constant_col.csv"), x_col="x", y_col="y")
    assert r["status"] == "ok"
    assert r["result"]["pearson_r"] is None
    assert "不可计算" in r["summary"]


def test_json_safe():
    r = plot_scatter(str(SAMPLES / "clean.csv"), x_col="age", y_col="income")
    json.dumps(r, allow_nan=False, ensure_ascii=False)
