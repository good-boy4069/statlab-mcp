# -*- coding: utf-8 -*-
"""生成 tests/fixtures/ 测试数据（固定 seed，入库防 seed 漂移）。

单一 seed 源：复用 samples/make_sample_data.py 的生成函数（红队 I7 裁决），
再叠加测试专用变体（重复列名/中文列名/常量列/单行/空文件占位）。
用法：在项目根运行  .venv\\Scripts\\python.exe tests\\make_fixtures.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from samples.make_sample_data import SEED, make_clean, make_dirty, make_timeseries

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"


def make_special() -> "dict[str, pd.DataFrame]":
    """测试专用变体（samples 之外）。"""
    rng = np.random.default_rng(SEED + 3)
    n = 12
    return {
        "dup_columns.csv": pd.DataFrame(
            np.arange(n * 3).reshape(n, 3), columns=["a", "a", "b"]),
        "chinese_columns.csv": pd.DataFrame({
            "姓名": rng.choice(["张三", "李四", "王五"], n),
            "成绩": np.round(rng.normal(80, 10, n), 2),
        }),
        "constant_col.csv": pd.DataFrame({
            "x": np.ones(n), "y": np.round(rng.normal(0, 1, n), 3)}),
        "single_row.csv": pd.DataFrame({"x": [1.0], "y": [2.0]}),
        "tiny_numeric.csv": pd.DataFrame({
            "a": [1.0, 2.0, 3.0, 4.0], "b": [4.0, 3.0, 2.0, 1.0]}),
    }


if __name__ == "__main__":
    FIX.mkdir(exist_ok=True)
    files = {
        "clean.csv": make_clean(),
        "dirty.csv": make_dirty(),
        "timeseries.csv": make_timeseries(),
        **make_special(),
    }
    for fname, df in files.items():
        df.to_csv(FIX / fname, index=False, encoding="utf-8-sig")
        print(f"fixtures/{fname}: shape={df.shape}")
    empty = FIX / "empty.csv"
    empty.write_text("", encoding="utf-8")          # 空文件（0 字节）
    header = FIX / "header_only.csv"
    header.write_text("a,b,c\n", encoding="utf-8")  # 仅表头
    print(f"fixtures/empty.csv (0B), fixtures/header_only.csv")
    print("FIXTURES-GENERATED seed=42")