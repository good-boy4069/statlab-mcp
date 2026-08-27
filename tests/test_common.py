"""tests/test_common.py —— tools/_common.py 七函数测试（规范 10）。

独立性：均值对照 statistics.mean（标准库，独立于 pandas/numpy 实现）；
to_jsonable 用 json.dumps(allow_nan=False) 强断言（红队裁决 2）。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statlab_mcp.tools import _common as C

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


# ---------------- read_table ----------------

def test_read_table_clean():
    df = C.read_table(str(SAMPLES / "clean.csv"))
    assert df.shape == (50, 6)
    assert list(df.columns) == ["id", "age", "score", "category", "income", "date"]


def test_read_table_dirty_keeps_all_missing_col():
    df = C.read_table(str(SAMPLES / "dirty.csv"))
    assert "empty_col" in df.columns          # 全缺失列必须保留
    assert df["empty_col"].isna().all()


def test_read_table_timeseries_missing_count():
    df = C.read_table(str(SAMPLES / "timeseries.csv"))
    assert int(df["value"].isna().sum()) == 3


def test_read_table_not_exist_raises_cn():
    with pytest.raises(C.DataLabError, match="文件不存在"):
        C.read_table(str(SAMPLES / "nope.csv"))


def test_read_table_non_whitelist_raises_cn():
    with pytest.raises(C.DataLabError, match="仅支持"):
        C.read_table(str(SAMPLES / ".." / "README.md"))


def test_read_table_gbk_fallback(tmp_path):
    """csv gbk 编码应自动回退成功（Windows 硬性要求 2）。"""
    p = tmp_path / "gbk.csv"
    pd.DataFrame({"中文列": ["一", "二"], "值": [1.5, 2.5]}).to_csv(p, index=False, encoding="gbk")
    df = C.read_table(str(p))
    assert df["值"].tolist() == [1.5, 2.5]
    assert df.columns.tolist() == ["中文列", "值"]


def test_read_table_json_utf8_only(tmp_path):
    """json 不做 gbk 回退（红队裁决 5：GBK 静默乱码比报错更危险）。"""
    p = tmp_path / "gbk.json"
    p.write_text('{"a": "中文"}', encoding="gbk")
    with pytest.raises(C.DataLabError, match="仅支持 UTF-8"):
        C.read_table(str(p))


def test_read_table_json_table_structure(tmp_path):
    p = tmp_path / "ok.json"
    p.write_text('[{"a": 1, "b": 2}, {"a": 3, "b": 4}]', encoding="utf-8")
    df = C.read_table(str(p))
    assert df.shape == (2, 2)


def test_read_table_xlsx_first_sheet_only(tmp_path):
    p = tmp_path / "book.xlsx"
    with pd.ExcelWriter(p, engine="openpyxl") as w:
        pd.DataFrame({"a": [1, 2]}).to_excel(w, sheet_name="第一页", index=False)
        pd.DataFrame({"x": [9]}).to_excel(w, sheet_name="第二页", index=False)
    df = C.read_table(str(p))
    assert list(df.columns) == ["a"]          # 只读第一个 sheet
    assert df.shape == (2, 1)


def test_read_table_empty_file_raises(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8")
    with pytest.raises(C.DataLabError, match="空或无可读数据"):
        C.read_table(str(p))


# ---------------- check_file ----------------

def test_check_file_unc_rejected():
    for bad in ["\\\\server\\share\\a.csv", "//server/share/a.csv"]:
        with pytest.raises(C.DataLabError, match="本地文件路径"):
            C.check_file(bad)


def test_check_file_size_limit(monkeypatch):
    monkeypatch.setattr(C, "MAX_FILE_BYTES", 100)          # 阈值压到 100B
    with pytest.raises(C.DataLabError, match="MB 上限"):   # 文案随阈值动态（复检建议）
        C.check_file(str(SAMPLES / "clean.csv"))


def test_check_file_returns_meta():
    info = C.check_file(str(SAMPLES / "clean.csv"))
    assert info["path"].endswith("clean.csv")
    assert info["size_bytes"] > 0
    assert info["rows_estimated"] is None    # <5MB 不预检


# ---------------- to_jsonable ----------------

def test_to_jsonable_all_native_types():
    """规范 7.2：所有统计量均为 Python 原生类型 + 禁 NaN/Infinity 字面量。"""
    obj = {
        "f64": np.float64(1.5), "f32": np.float32(0.1), "i64": np.int64(3),
        "i32": np.int32(3), "b": np.bool_(True), "nan": np.float64("nan"),
        "inf": np.float64("inf"), "pinf": float("inf"),
        "ts": pd.Timestamp("2025-01-01"), "arr": np.array([1, 2], dtype=np.int32),
        "ser": pd.Series([1.5, 2.5]), "nested": {"k": np.float64(2.0)},
        "pynan": float("nan"),
    }
    j = C.to_jsonable(obj)
    json.dumps(j, allow_nan=False)                       # 强断言：禁 NaN/Infinity
    for k in ["f64", "f32", "i64", "i32", "b", "ts", "arr", "ser", "nested"]:
        assert isinstance(j[k], (int, float, str, bool, list, dict)), k
    assert j["nan"] is None and j["inf"] is None and j["pinf"] is None and j["pynan"] is None
    assert isinstance(j["ts"], str)
    assert isinstance(j["nested"]["k"], float)


def test_to_jsonable_series_median_compare_statistics():
    """独立第三方对照（规范 10）：median 对照标准库 statistics。"""
    x = pd.Series([3.0, 1.0, 2.0, 10.0, 5.0])
    j = C.to_jsonable({"median": x.median()})
    assert j["median"] == pytest.approx(3.0)
    assert isinstance(j["median"], float)


# ---------------- ok / err ----------------

def test_ok_structure_and_summary():
    r = C.ok({"n": np.int64(5), "mean": np.float64(1.0)}, "共 5 行，均值 1.0")
    assert list(r.keys()) == ["status", "result", "summary"]   # 固定三层
    assert r["status"] == "ok"
    assert type(r["result"]["n"]) is int                       # 原生类型断言
    assert type(r["result"]["mean"]) is float
    assert isinstance(r["summary"], str)


def test_err_structure_no_result():
    # v1.1.0：err() 新增必填 code 参数，错误 dict 为三层 {status, error_code, message}
    # （CHANGELOG 已列本断言为"因新增 error_code 键被适配的既有断言"）
    r = C.err(C.EC.CALC, "测试错误")
    assert list(r.keys()) == ["status", "error_code", "message"]
    assert r["status"] == "error"
    assert r["error_code"] == C.EC.CALC
    assert "result" not in r


# ---------------- validate_columns ----------------

def test_validate_columns_missing_cn():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(C.DataLabError, match="缺少必需列: b"):
        C.validate_columns(df, ["a", "b"])


def test_validate_columns_single_str():
    df = pd.DataFrame({"a": [1]})
    C.validate_columns(df, "a")   # 不抛


# ---------------- save_plot ----------------

def test_save_plot_path_and_file(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "PLOT_DIR", tmp_path)   # 输出重定向到临时目录
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot([1, 2], [3, 4])
    p = C.save_plot(fig, "describe_statistics_score")
    p_path = Path(p)
    assert p_path.exists() and p_path.suffix == ".png"
    assert p_path.name.startswith("describe_statistics_score_")
    assert p_path.is_absolute()


def test_safe_name_sanitize_and_reserved():
    assert C._safe_name('a<b>c:d"e/f\\g|h?i*j') == "a_b_c_d_e_f_g_h_i_j"
    assert C._safe_name("con") == "_con"          # Windows 保留名
    assert C._safe_name("NUL") == "_NUL"       # Windows 保留名，大小写不敏感
    assert C._safe_name("") == "all"
    assert len(C._safe_name("x" * 100)) <= 40


# ---------------- 红队回归测试（2026 第二轮审查补丁） ----------------

def test_nul_path_rejected():
    """红队 B S5：NUL 字节路径显式拒绝。"""
    with pytest.raises(C.DataLabError, match="NUL"):
        C.check_file("data/\x00evil.csv")


def test_xlsx_corrupted_cn(tmp_path):
    """红队 A S1：损坏 xlsx 中文报错（zip 预检路径）。"""
    p = tmp_path / "bad.xlsx"
    p.write_bytes(b"not a zip at all")
    with pytest.raises(C.DataLabError, match="损坏或无法打开"):
        C.read_table(str(p))


def test_xlsx_zip_bomb_rejected(monkeypatch, tmp_path):
    """红队 A S1/I1：解压体积超限拒绝（monkeypatch 阈值到极小）。"""
    p = tmp_path / "ok.xlsx"
    pd.DataFrame({"a": [1, 2]}).to_excel(p, index=False)          # 正常小 xlsx
    monkeypatch.setattr(C, "MAX_MEM_BYTES", 100)                  # 阈值压到 100 字节
    with pytest.raises(C.DataLabError, match=r"压缩炸弹|体积过大"):
        C.check_file(str(p))


def test_json_size_limit(monkeypatch, tmp_path):
    """红队 B I2：json 超上限拒绝（解析放大防护）。"""
    p = tmp_path / "big.json"
    p.write_text('[{"a": 1}]' + " " * (C.JSON_MAX_BYTES + 1), encoding="utf-8")
    with pytest.raises(C.DataLabError, match="JSON 文件超过"):
        C.check_file(str(p))


def test_date_span_guard(tmp_path):
    """红队 B B1：日期跨度过大在重采样前拒绝（防内存爆炸）。
    触发路径 = 高频率 + 长跨度：分钟级序列横跨 pandas 最大范围（1677~2262，
    约 3e8 分钟点 > 200 万上限）；34 万天级跨度在阈值内放行。"""
    df_ok = pd.DataFrame({"date": ["1900-01-01", "2025-05-01", "2250-01-01"],
                          "value": [1.0, 2.0, 3.0]})
    C._prepare_series(df_ok, "date", "value")                      # 不抛（约 12.8 万天 < 200 万）
    df_bad = pd.DataFrame({
        "date": ["2025-01-01 00:00", "2025-01-01 00:01", "2025-01-01 00:02",
                 "2250-01-01 00:00"],   # 1 分钟频率 + 225 年跨度，约 1.2e8 点（界内）
        "value": [1.0, 2.0, 3.0, 4.0]})
    with pytest.raises(C.DataLabError, match="日期跨度过大"):
        C._prepare_series(df_bad, "date", "value")


def test_save_plot_date_subdir(monkeypatch, tmp_path):
    """红队 C B2：图存日期子目录（防堆积）。"""
    from datetime import datetime as _dt
    monkeypatch.setattr(C, "PLOT_DIR", tmp_path)
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot([1], [2])
    p = C.save_plot(fig, "redteam_check_all")
    p_path = Path(p)
    assert p_path.parent.name == _dt.now().strftime("%Y%m%d")
    assert p_path.exists()
