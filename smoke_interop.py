# -*- coding: utf-8 -*-
"""互操作冒烟测试：验证依赖栈在 Python 3.13 + pandas 3.0.5 下真实运行兼容。

来源：红队审查 B1 修复集（pandas 3.0 为大版本，依赖声明只保证装得上不保证跑得动）。
运行：.venv\\Scripts\\python.exe smoke_interop.py
任一环节抛异常即视为冒烟失败 → 降级 pandas==2.3.* 重装并复跑。
"""
import sys

def step(name):
    print(f"[SMOKE] {name} ...", flush=True)

# ① 全量 import
step("import 全依赖")
import numpy as np
import pandas as pd
import scipy
import statsmodels.api as sm
import sklearn
import matplotlib
import matplotlib.pyplot as plt
import pmdarima
import openpyxl
import pytest
import mcp
from importlib.metadata import version as _v
print(f"  versions: numpy={np.__version__} pandas={pd.__version__} scipy={scipy.__version__} "
      f"statsmodels={sm.__version__} sklearn={sklearn.__version__} matplotlib={matplotlib.__version__} "
      f"pmdarima={pmdarima.__version__} openpyxl={openpyxl.__version__} mcp={_v('mcp')} pytest={pytest.__version__}")

# ② pandas 3.0 核心行为 + statsmodels OLS 真实拟合（str 列 + NaN）
step("DataFrame 构造/groupby/describe + statsmodels OLS")
df = pd.DataFrame({
    "y": [1.0, 2.5, 3.0, 4.2, 5.1, 6.0, 7.3, 8.0],
    "x": [1, 2, 3, 4, 5, 6, 7, 8],
    "cat": ["a", "b", "a", "b", "a", "b", "a", "b"],
    "miss": [1.0, np.nan, 3.0, np.nan, 5.0, 6.0, np.nan, 8.0],
})
g = df.groupby("cat")["y"].mean()
d = df.describe()
X = sm.add_constant(df[["x", "miss"]])
fit = sm.OLS(df["y"], X, missing="drop").fit()
print(f"  groupby={dict(g)}; describe_rows={len(d)}")
print(f"  OLS params={list(fit.params)} pvalues={list(fit.pvalues)} r2={fit.rsquared:.4f}")
ci = fit.conf_int()
print(f"  OLS conf_int shape={ci.shape}")

# ③ pmdarima 最小拟合（ARIMA 兜底，避免 auto_arima 在最小数据过慢）
step("pmdarima ARIMA(1,0,0) 拟合")
s = pd.Series([float(i) + np.sin(i / 3.0) for i in range(20)])
model = pmdarima.ARIMA(order=(1, 0, 0)).fit(s)
fc, fc_ci = model.predict(n_periods=3, return_conf_int=True)
print(f"  forecast={list(np.round(fc, 3))}")

# ④ sklearn 切分 + 聚类
step("sklearn train_test_split + KMeans")
from sklearn.model_selection import train_test_split
from sklearn.cluster import KMeans
Xa = df[["x", "miss"]].fillna(0.0)
tr, te = train_test_split(Xa, test_size=0.3, random_state=42, stratify=None)
km = KMeans(n_clusters=2, random_state=42, n_init="auto").fit(tr)
print(f"  split {len(tr)}/{len(te)}; kmeans labels={sorted(km.labels_.tolist())}")

# ⑤ read_excel + describe（openpyxl 引擎）
step("pd.read_excel + describe")
xlsx_path = "_smoke_tmp.xlsx"
df.to_excel(xlsx_path, index=False, sheet_name="s1")
df2 = pd.read_excel(xlsx_path, sheet_name=0, engine="openpyxl")
import os
os.remove(xlsx_path)
print(f"  read_excel shape={df2.shape}; describe ok={len(df2.describe()) == 8}")

# ⑥ matplotlib Agg + 中文配置探测（供 save_plot 参考）
step("matplotlib Agg 后端 + 中文字体探测")
matplotlib.use("Agg")
from matplotlib import font_manager
cjk_names = ["Microsoft YaHei", "SimHei"]
found = [n for n in cjk_names if any(f.name == n for f in font_manager.fontManager.ttflist)]
print(f"  CJK fonts found: {found or 'NONE -> 将降级英文标签'}")

print("[SMOKE] ALL-INTEROP-OK")