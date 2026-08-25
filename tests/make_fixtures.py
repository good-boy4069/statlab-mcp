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


def make_binary() -> "dict[str, pd.DataFrame]":
    """二分类建模专用（seed 固定入库）：
    - binary_noisy.csv：120 行，score 加噪决定标签（收敛、AUC 中等）
    - binary_separable.csv：80 行，score 阈值完美分隔（触发分离警告）
    """
    rng = np.random.default_rng(SEED + 4)
    n = 120
    score = np.round(rng.normal(55, 12, n), 1)
    noise = rng.normal(0, 6, n)
    label = (score + noise > 56).astype(int)
    noisy = pd.DataFrame({"score": score, "age": rng.integers(18, 65, n), "label": label})

    rng2 = np.random.default_rng(SEED + 5)
    n2 = 80
    s2 = np.round(rng2.normal(50, 10, n2), 1)
    l2 = (s2 > 50).astype(int)                  # 完美可分
    separable = pd.DataFrame({"score": s2, "label": l2})
    return {"binary_noisy.csv": noisy, "binary_separable.csv": separable}


if __name__ == "__main__":
    FIX.mkdir(exist_ok=True)
    files = {
        "clean.csv": make_clean(),
        "dirty.csv": make_dirty(),
        "timeseries.csv": make_timeseries(),
        **make_special(),
        **make_binary(),
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