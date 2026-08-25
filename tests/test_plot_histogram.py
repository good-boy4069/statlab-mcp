"""tests/test_plot_histogram.py —— 工具 22 测试。
独立性：mean/std 与 describe_statistics 交叉核对；分箱数公式断言。
"""
import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools.visualization_plot_histogram import plot_histogram

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def test_clean_histogram_cross_check():
    r = plot_histogram(str(SAMPLES / "clean.csv"), column="score")
    assert r["status"] == "ok", r.get("message")
    rs = r["result"]
    assert rs["n"] == 50 and rs["bins"] == min(40, max(8, math.ceil(math.sqrt(50))))
    from statlab_mcp.tools.data_exploration_describe_statistics import (
        describe_statistics,
    )
    d = describe_statistics(str(SAMPLES / "clean.csv"))["result"]["columns"]["score"]
    assert rs["mean"] == pytest.approx(d["mean"])
    assert rs["std"] == pytest.approx(d["std"])
    img = Path(r["__image__"])
    assert img.suffix == ".png" and img.exists()


def test_errors():
    assert "缺少必需列" in plot_histogram(str(SAMPLES / "clean.csv"),
                                           column="nope")["message"]
    assert "不是数值列" in plot_histogram(str(SAMPLES / "clean.csv"),
                                           column="category")["message"]
    assert "至少需要 2 个有效值" in plot_histogram(
        str(ROOT / "tests" / "fixtures" / "single_row.csv"), column="x")["message"]
    assert plot_histogram(str(SAMPLES / "nope.csv"), column="x")["status"] == "error"


def test_json_safe():
    r = plot_histogram(str(SAMPLES / "clean.csv"), column="income")
    json.dumps(r, allow_nan=False, ensure_ascii=False)
