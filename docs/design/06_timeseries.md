# 时序组 · 接口设计文档（整组交付）

> 交付物：time_series_forecast / seasonal_decompose / trend_analysis / anomaly_detect。
> 规格 17-20 均为【简化】实现：只做"能出真实数字的最小可靠版本"，每个工具注明略过内容。
> 全局约定沿用前组：error 无 result；原生类型；NaN→null；summary 模板；确定性可复现。

## 五项统一前置（规格硬性，实现为 tools/_common.py 的 _prepare_series() 公共预处理器）

所有时序工具的第一步共用同一预处理器，输入 (df, date_col, value_col)，输出 (Series, meta)：
1. **日期解析**：`pd.to_datetime(date_col, errors="coerce")`；无法解析的日期行**剔除并计数**（"已剔除 N 行非法日期"）；全失败 → error："日期列无法解析"
2. **重复时间戳**：检测重复 → 按日聚合（`resample("D").sum()`，规则固定为 sum 并在 summary 注明"重复时间戳已按天求和聚合，合并 N 行"；如原始已为日内频率则说明）
3. **缺失显式处理**：重采样到固定频率（`pd.infer_freq` 失败则取相邻间隔的中位数作为周期，注明"频率由间隔中位数推断，为 X"）→ `asfreq` → **线性插值** `interpolate()`（仅在中间缺失；两端缺失保留 NaN 并注明）→ 报告 **"已插值 N 个缺失点"**，禁止静默 dropna
4. **horizon 上限**（forecast 专用）：horizon ≤ 样本量×50%，超限 error："horizon=N 超过样本量一半（M），请降低预测步数"
5. **时区**：t-aware 日期列 → `tz_convert("UTC")` 并标注"已统一为 UTC"；naive 不处理
另：样本量门槛 n<15 → error："样本过短（n=N<15），时序分析不可靠"（17/18/20 适用；19 用 n<8）。

公共输出 meta：{n, dropped_invalid_dates, merged_duplicates, interpolated, freq, utc_note}。

---

# 工具 17：time_series_forecast(file_path, date_col, value_col, horizon)【简化】

一句话用途：预测未来 N 步（值+95% 置信区间），画历史+预测图。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局 | `file_path="timeseries.csv"` |
| date_col / value_col | str | 必填 | 均须存在且 value 为数值列 | `date_col="date"` |
| horizon | int | 必填 | 1 ≤ horizon ≤ n×50%（前置 4）；整数 | `horizon=14` |

## 方法与口径（钉死）
1. **自动定阶**：`pmdarima.auto_arima(y, seasonal=可估, m=period, stepwise=True,
   suppress_warnings=True, error_action="ignore", max_order=8, random_state=42)`；
   **季节可估判定（前置 3）**：n ≥ 2×period（period 推断见下）才 seasonal=True，否则 ARIMA
   （季节样本不足时注明"季节不可估，已用 ARIMA"）
2. **period 推断**：FFT 主频法（去线性趋势后 `np.fft.rfft`，排除频率 0 与最末 bin，
   取最大幅度对应的周期 round(1/f)；2 ≤ period ≤ n/2，否则视为无可估季节）
3. p 值质量：拟合对象输出 model.order/m/seasonal_order、AIC；预测 `predict(n_periods=horizon,
   return_conf_int=True)` 95% CI
4. **图**（附录 D）：历史实线 + 预测虚线 + CI 填充带（`__image__` 顶层）
5. 结论模板：`ARIMA(p,d,q)(P,D,Q,m)：未来 N 步预测（第 1 步=value，95% CI [lo, hi]）；AIC=x`

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "n": 120, "horizon": 14, "freq": "D",
    "model": {"order": [1,0,1], "seasonal_order": [1,0,0,30], "seasonal": true, "aic": 780.2},
    "method": "SARIMA" | "ARIMA",
    "metadata": {...五项前置 meta...},
    "forecast": [{"step": 1, "value": 32.1, "ci_lower": 28.3, "ci_upper": 35.9}, ...],
    "last_observed": {"date": "2025-04-30", "value": 31.8},
    "conclusion": "未来 14 步预测完成；第 1 步预测 32.1（95% CI [28.3, 35.9]）"
  },
  "__image__": "C:\\...\\forecast_time_series_forecast_all_20260826_123456.png",
  "summary": "SARIMA(1,0,1)(1,0,0,30)：预测 14 步，第一步 32.1（CI [28.3, 35.9]）；AIC 780；已插值 3 个缺失点；相关≠因果"
}
```

## 边界行为表
| 场景 | 行为 |
|---|---|
| horizon 越界 / 非整数 | error（前置 4 + "horizon 必须是整数"） |
| n<15 | error："样本过短（n=N<15）" |
| 全缺失值列 | error："value 列无有效数据" |
| 常数序列 | ARIMA 退化（无 AR 效应），预测=常数，注明"常数列预测退化为均值" |
| 季节不可估 | 注明并退 ARIMA（见口径 1） |
| 中文列名 | 键原样；图文件名清洗 |

## 错误路径（≥3 种）
1. `horizon=60 超过样本量一半（60），请降低预测步数`（n=120, horizon=61 时）
2. `样本过短（n=10<15），时序分析不可靠`
3. `日期列无法解析`
4. `value 列无有效数据`

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.timeseries_time_series_forecast import time_series_forecast; import json; print(json.dumps(time_series_forecast('samples/timeseries.csv', date_col='date', value_col='value', horizon=14), ensure_ascii=False, indent=1))"
```
- timeseries.csv = 趋势+周期 30+噪声（seed 42 固定）→ 预测值应落在趋势延伸附近（语义核验）；
  AIC/参数为库真实值；"已插值 3 个缺失点"应为 3（人工核数）
- 【简化】略过：不做滚动回测、不做多模型对比、CI 为库正态近似（不注明不校准）

---

# 工具 18：seasonal_decompose(file_path, date_col, value_col, period=None, model="auto")【简化】

一句话用途：把序列拆成 趋势 + 季节 + 残差 三部分，看周期性规律。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局 | 例子 |
| date_col / value_col | str | 必填 | 同上 | 例子 |
| period | int\|None | None | 显式时 ≥2 且 ≤n/2（否则中文报错）；默认自动估计（FFT 主频，同 17 口径 2） | `period=30` |
| model | str | "auto" | ∈ {additive, multiplicative, auto}；auto = 全正值→multiplicative 否则 additive（注明选择依据） | `model="multiplicative"` |

## 方法（钉死）
1. `statsmodels.tsa.seasonal.seasonal_decompose(y, model=选定, period=period, extrapolate_trend="freq")`
2. **multiplicative 要求全正值**：有 ≤0 且 model=multiplicative → error："乘法分解要求全正值，请改用 additive"；auto 时遇 ≤0 → additive + 注明"含非正值，已改用加法"
3. 输出：`components`（trend/seasonal/resid 的均值、最近值）、季节因子最后一周期的逐点值、resid 的 std（异常诊断参考）；**图**（4 子图：原值/趋势/季节/残差，`__image__` 顶层）
4. 结论模板：`{additive|multiplicative} 分解，周期={period}；季节幅度 ≈{max-min}；残差 std={σ}`（注明"分解基于固定周期假设"）

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "period": 30, "model": "additive", "n": 120,
    "metadata": {...},
    "components": {"trend": {"mean": 22.5, "last": 34.8},
                   "seasonal": {"mean": 0.0, "last": 1.2, "amplitude": 9.4},
                   "resid": {"mean": 0.0, "std": 1.5, "n_nan": 0}},
    "seasonal_factors": [1.2, -2.1, ...],   // 最后完整周期
    "conclusion": "additive 分解（周期 30）：季节波动幅度 ±9.4，残差 std 1.5"
  },
  "__image__": "...seasonal_decompose_all_....png",
  "summary": "加法分解，周期 30：趋势 10→35、季节幅度 ±9.4、残差 σ=1.5；已插值 3 个缺失点"
}
```

## 边界行为表
| 场景 | 行为 |
|---|---|
| period 越界 / 非整数 | error："period 必须在 2 到 n/2 之间" / "period 必须是整数" |
| 自动估计失败（无周期） | period=1 报 error："无法估计周期，请显式指定 period" |
| multiplicative + 非正值 | error（见口径 2） |
| 残差两端 NaN（分解首尾） | n_nan 如实报告，不报错 |
| 常数列 | 趋势=常数、季节幅度 0，正常输出 |

## 错误路径（≥3 种）
1. `period 必须在 2 到 n/2 之间`
2. `乘法分解要求全正值，请改用 additive`
3. `无法估计周期，请显式指定 period`
4. `样本过短（n=N<15）`

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.timeseries_seasonal_decompose import seasonal_decompose; import json; print(json.dumps(seasonal_decompose('samples/timeseries.csv', date_col='date', value_col='value'), ensure_ascii=False, indent=1))"
```
- timeseries.csv 生成公式已知：趋势 linspace(10,35) + 5·sin(2π·t/30) + 噪声
  → **期望 period=30**？FFT 主频应检出 30；**季节幅度**：理论 10，但相位平均仅 4 点/相位
  （120/30），噪声极值统计使估计天然偏大（实测 11~13）——断言取统计区间；
  趋势两段值≈10/35——数学事实核验点！

---

# 工具 19：trend_analysis(file_path, date_col, value_col, method="mann_kendall")【简化】

一句话用途：回答"序列整体在上升/下降吗？显著吗？斜率多大？"

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局 | 例子 |
| date_col / value_col | str | 必填 | 同上 | 例子 |
| method | str | "mann_kendall" | ∈ {mann_kendall, theil_sen}；非法报错 | `method="theil_sen"` |

## 方法（钉死）
1. **Mann-Kendall**：`scipy.stats.kendalltau(y, np.arange(n))` 的 tau 与 p（MK 检验的 tau 统计量 + 正态近似 p，scipy 官方实现，输出注明该口径；p 双侧）
2. **Theil-Sen 斜率**：所有点对斜率 `(y_j−y_i)/(t_j−t_i)` 的中位数；n≤2000 全量枚举，n>2000 用固定 seed 抽样 50000 对并注明"大样本已抽样"
3. 输出：method_used、tau、p_value、slope（Theil-Sen，两种方法都输出斜率）、n、
   `trend_direction`（slope>0：上升 / <0：下降 / ≈0：无）、`monotonic`（p<0.05 有显著单调趋势 + 方向）
4. 结论模板：`Mann-Kendall：tau={x}, p={y}，{显著上升|显著下降|无显著单调趋势}；斜率（Theil-Sen）=z/单位时间`
5. 【简化】略过：不输出置信区间、不做季节校正（注明"含季节成分时趋势结论需谨慎"）

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "method": "mann_kendall", "n": 120,
    "tau": 0.93, "p_value": 0.0001,
    "slope": 0.23, "slope_note": "Theil-Sen 中点对斜率中位数",
    "trend_direction": "上升", "monotonic": true,
    "conclusion": "p<0.001 存在显著上升的单调趋势；每单位时间+0.23"
  },
  "summary": "Mann-Kendall：tau=0.93（p<0.001）显著上升趋势；Theil-Sen 斜率 0.23/天；已插值 3 个缺失点"
}
```

## 边界行为表
| 场景 | 行为 |
|---|---|
| n<8 | error："样本过短（n=N<8），趋势检验不可靠" |
| 常数序列 | tau=0、p=1、slope=0，正常输出 |
| 含季节 | 注明"含季节成分时趋势结论需谨慎"（不校正） |
| 缺失 | 前置插值后无缺失（已注) |

## 错误路径（≥3 种）
1. `method 仅支持 mann_kendall/theil_sen`
2. `样本过短（n=N<8），趋势检验不可靠`
3. `日期列无法解析`

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.timeseries_trend_analysis import trend_analysis; import json; print(json.dumps(trend_analysis('samples/timeseries.csv', date_col='date', value_col='value'), ensure_ascii=False, indent=1))"
```
- timeseries.csv 已知趋势 linspace(10,35)/119 天 → **Theil-Sen 斜率 ≈ 0.21~0.23**（手算范围可核）；
  tau 应显著为正（p<0.001）——语义核验点

---

# 工具 20：anomaly_detect(file_path, date_col, value_col, method="stl", threshold=3.0)【简化】

一句话用途：时序里找"突然跳变"的点（不同于 outlier_detect 的静态离群），输出异常点位置与区间图；**绝不自动剔除**。

## 参数表
| 参数名 | 类型 | 默认值 | 校验规则 | 例子 |
|---|---|---|---|---|
| file_path | str | 必填 | 同全局 | 例子 |
| date_col / value_col | str | 必填 | 同上 | 例子 |
| method | str | "stl" | ∈ {stl, iqr, rolling_zscore} | `method="rolling_zscore"` |
| threshold | float | 3.0 | >0；≤0 报错"threshold 必须 >0" | `threshold=2.5` |

## 方法（钉死）
1. **stl**（默认）：`statsmodels.tsa.seasonal.STL(y, period=周期(FFT 法), robust=True)` →
   残差 `|resid| > threshold × resid.std(ddof=1)` 的点为异常（**实现期修订**：判据尺度用
   残差标准差而非 MAD——MAD 对"主体集中+稀疏厚尾"的残差分布严重低估尺度，实测
   timeseries 产出 31 个假阳性而 std 版仅 2 个；std 判据与 threshold=3 的 3σ 语义一致）
2. **iqr**：一阶差分序列 `diff=y.diff()` 上 IQR 规则（Q1−1.5IQR/Q3+1.5IQR，同探查组口径），
   异常索引映射回原行号
3. **rolling_zscore**：窗口 7 滚动 mean/std（min_periods=3），`|z|>threshold`
4. 输出：`anomalies: [{index, date, value, resid|z|diff, note}]`（按时间序）、`n_anomalies`、
   `method_used`；**图**（原值线 + 异常红点 + stl 时残差参考线带，`__image__` 顶层）；
   summary 注明"异常点仅报告不剔除"
5. 【简化】略过：不做区间校准、不做多方法融合（结果以所选手法为准）

## 返回（成功）
```jsonc
{
  "status": "ok",
  "result": {
    "method": "stl", "threshold": 3.0, "n": 119, "period": 30,
    "n_anomalies": 3,
    "anomalies": [{"index": 17, "date": "2025-01-18", "value": 28.4, "resid": 6.1}],
    "note": "异常判据：|残差| > 3.0×稳健残差标准差；仅报告不剔除"
  },
  "__image__": "...anomaly_detect_all_....png",
  "summary": "STL 残差法检出 3 个异常点（2025-01-18 等）；threshold=3.0；异常仅报告不剔除"
}
```

## 边界行为表
| 场景 | 行为 |
|---|---|
| threshold ≤0 | error："threshold 必须 >0" |
| 常数序列 | 残差全 0 → 无异常（std=0 防护），注明 |
| 方法非法 | error："method 仅支持 stl/iqr/rolling_zscore" |
| 季节不可估 | stl 退化为"残差=去趋势"（period 估计失败时用阶数 1 差分处理后残差，注明） |
| 无异常 | n_anomalies=0，图照存，summary 注明"未发现异常" |

## 错误路径（≥3 种）
1. `method 仅支持 stl/iqr/rolling_zscore`
2. `threshold 必须 >0`
3. `样本过短（n=N<15）`

## 验证命令与预期值来源
```powershell
& .\.venv\Scripts\python.exe -c "from statlab_mcp.tools.timeseries_anomaly_detect import anomaly_detect; import json; print(json.dumps(anomaly_detect('samples/timeseries.csv', date_col='date', value_col='value'), ensure_ascii=False, indent=1))"
```
- timeseries 是平滑序列（σ=1.5 噪声 + 3 缺失插值）→ 预期异常 0~2 个（3.0σ 阈值）；
  rolling_zscore 与 stl 结果应都极少——语义核验 + 方法间一致性

---

# 附录：时序组自查（附录 C 组内 3 问）
- ⑦ 参数风格一致：date_col/value_col 统一；period/threshold/horizon 均有整数/范围校验
- ⑧ 无重叠：17 预测 / 18 分解 / 19 趋势 / 20 异常四象限独立；与探查组 outlier_detect（静态 IQR）区分——本组是**时序语境**（差分/残差/滚动窗）；与可视化组 plot_forecast（24 仅作图）不重复计算
- ⑨ 使用条件写明：ARIMA 需平稳性（auto_arima 自动差分）、分解需固定周期、MK 无季节校正（注明）、STL 需周期可估——全部落入输出与边界表

## 大白话三问（附录 C 必答）
1. **能在 Excel 里验证吗？** 部分能：Theil-Sen 斜率可手算（两两斜率取中位数，小样本 Excel 可做）；
   Mann-Kendall 的 tau 用 Excel 可逐步算但繁琐（以 scipy 为准）。ARIMA/STL 是迭代算法——
   以构造数据的语义结论（`timeseries.csv` 已知公式：趋势 10→35、周期 30、幅度 ±5、σ=1.5）为准。
2. **真实数据接得住吗？** 接得住。日期格式五花八门（to_datetime 容错）、重复时间戳自动按天聚合、
   缺失显式插值并报告、时区统一 UTC、非法日期行剔除计数——全部在 summary 里明示。
3. **同一文件跑两次一样吗？** 一样。auto_arima 传 random_state=42（定阶搜索确定性）、FFT/插值/
   STL 均无随机性；仅"大样本斜率抽样"用固定 seed 且注明。