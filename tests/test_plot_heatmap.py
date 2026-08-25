"""tests/test_plot_heatmap.py —— 工具 23 测试。
独立性：矩阵与 correlation_matrix 的 r 交叉核对；常量列 r=null；对角=1.0。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.visualization_plot_heatmap import plot_heatmap

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
FIX = ROOT / "tests" / "fixtures"


def test_clean_heatmap_cross_check():
    r = plot_heatmap(str(SAMPLES / "clean.csv"))
    assert r["status"] == "ok", r.get("message")
    rs = r["result"]
    assert rs["numeric_columns"] == ["id", "age", "score", "income"]
    assert rs["excluded_columns"] == ["category", "date"]
    m = rs["matrix"]
    assert m["id"]["id"] == 1.0
    from statlab_mcp.tools.data_exploration_correlation_matrix import (
        correlation_matrix,
    )
    cm = correlation_matrix(str(SAMPLES / "clean.csv"))["result"]["correlation"]
    assert m["age"]["income"] == pytest.approx(cm["age"]["income"], abs=1e-12)
    img = Path(r["__image__"])
    assert img.suffix == ".png" and img.exists()


def test_constant_col_null():
    r = plot_heatmap(str(FIX / "constant_col.csv"))
    assert r["status"] == "ok"
    assert r["result"]["matrix"]["x"]["y"] is None     # 常量列相关无定义


def test_errors(tmp_path):
    import pandas as pd
    p = tmp_path / "one.csv"
    pd.DataFrame({"a": [1.0, 2.0]}).to_csv(p, index=False, encoding="utf-8-sig")
    r = plot_heatmap(str(p))
    assert r["status"] == "error" and "至少需要 2 个数值列" in r["message"]
    assert plot_heatmap(str(SAMPLES / "nope.csv"))["status"] == "error"


def test_json_safe():
    r = plot_heatmap(str(SAMPLES / "clean.csv"))
    json.dumps(r, allow_nan=False, ensure_ascii=False)
