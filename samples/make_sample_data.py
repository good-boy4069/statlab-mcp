# -*- coding: utf-8 -*-
"""生成 samples/ 样例数据（固定 seed=42），入库用于回归测试与冒烟测试。

用法：在项目根运行  .venv\\Scripts\\python.exe samples\\make_sample_data.py
产出：clean.csv / dirty.csv / timeseries.csv（均 utf-8-sig 编码，兼容 Excel 直开）
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
HERE = Path(__file__).resolve().parent


def make_clean() -> pd.DataFrame:
    """clean.csv：50 行 x 6 列，含数值/类别/日期，结构规整。"""
    rng = np.random.default_rng(SEED)
    n = 50
    dates = pd.date_range("2025-01-01", periods=n, freq="D") + pd.Timedelta(days=int(rng.integers(0, 5)))
    return pd.DataFrame({
        "id": np.arange(1, n + 1, dtype=int),
        "age": rng.integers(18, 65, n),
        "score": np.round(rng.normal(70, 12, n), 2),
        "category": rng.choice(["A", "B", "C"], n, p=[0.5, 0.3, 0.2]),
        "income": np.round(rng.normal(8000, 2000, n).clip(3000), 2),
        "date": dates.strftime("%Y-%m-%d"),
    })


def make_dirty() -> pd.DataFrame:
    """dirty.csv：20 行，含空单元格 / 全缺失列 / 非法日期 2024-02-30 / 极端值 1e9。"""
    rng = np.random.default_rng(SEED + 1)
    n = 20
    df = pd.DataFrame({
        "name": [f"row{i}" for i in range(n)],
        "value": np.round(rng.normal(50, 10, n), 2),
        "empty_col": [np.nan] * n,                          # 全缺失列
        "bad_date": ["2024-02-30" if i == 3 else f"2024-{int(rng.integers(1, 12)):02d}-{int(rng.integers(1, 28)):02d}"
                     for i in range(n)],
        "extreme": [1e9 if i == 5 else float(np.round(rng.normal(100, 15), 2)) for i in range(n)],
    })
    df.loc[0, "value"] = np.nan      # 空单元格
    df.loc[1, "name"] = ""           # 空字符串单元格
    df.loc[2, "extreme"] = np.nan    # 空单元格
    return df


def make_timeseries() -> pd.DataFrame:
    """timeseries.csv：120 天日频序列（趋势+周期30天+噪声），含 3 个随机缺失点。"""
    rng = np.random.default_rng(SEED + 2)
    n = 120
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    trend = np.linspace(10, 35, n)
    seasonal = 5 * np.sin(2 * np.pi * np.arange(n) / 30)
    noise = rng.normal(0, 1.5, n)
    values = np.round(trend + seasonal + noise, 2)
    values[rng.choice(n, 3, replace=False)] = np.nan       # 3 个随机缺失
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "value": values})


if __name__ == "__main__":
    out = {
        "clean.csv": make_clean(),
        "dirty.csv": make_dirty(),
        "timeseries.csv": make_timeseries(),
    }
    for fname, df in out.items():
        df.to_csv(HERE / fname, index=False, encoding="utf-8-sig")
        print(f"{fname}: shape={df.shape}")
    # 自检：缺失点数量
    ts = out["timeseries.csv"]["value"]
    print(f"timeseries 缺失点数 = {int(ts.isna().sum())} (应为 3)")
    print("SAMPLES-GENERATED seed=42")