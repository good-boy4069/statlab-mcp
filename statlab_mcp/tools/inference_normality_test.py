"""normality_test —— 统计推断组 · 正态性检验（工具 9，核心实现）。

docstring = agent 使用说明书，与 statlab_mcp/docs/design/03_inference_batch1.md 同步维护。

参数:
    file_path (str): 本地数据文件（csv/tsv/xlsx/json）
    column (str): 分析列（须为数值列）
    method (str, "auto"): auto / shapiro / dagostino
        auto: n<=5000 -> Shapiro-Wilk（scipy 官方建议 3~5000）；5000<n<=100000 ->
        D'Agostino-Pearson（scipy.stats.normaltest）；n>100000 -> 中文报错提示抽样

输出: method_used, n, statistic, p_value, skew（Fisher 样本偏度，同 describe）,
      kurtosis（超额峰度，正态=0）, normal（判定 = p_value > 0.05）,
      threshold_alpha（固定 0.05 并在输出注明）

边界: n<3 / 常数列（方差 0）/ 显式 shapiro 但 n>5000（scipy 限制）/
      dagostino 且 n<8（scipy 要求）/ 非数值或缺失列 —— 全部中文报错。

示例:
    normality_test("samples/clean.csv", column="score")
inline 数据:
    本工具支持可选 inline_data 参数（v1.2.0 起）：与 file_path 二选一，
    支持 records 数组或 {"header": [...], "rows": [[...], ...]} 对象两种形态；
    规模上限/类型域/data_source 来源标注见 statlab_mcp/docs/SPEC.md 第 12 节。

"""

import pandas as pd
from scipy import stats as sps

from statlab_mcp.tools._common import EC, DataLabError, err, ok, require_non_none, resolve_data

_METHODS = {"auto", "shapiro", "dagostino"}
SHAPIRO_MIN_N, SHAPIRO_MAX_N = 3, 5000
DAGOSTINO_MIN_N, DAGOSTINO_MAX_N = 8, 100_000
ALPHA = 0.05


def _fmt_p(p: float) -> str:
    """p 值格式化：p<0.001 统一显示 '<0.001'（防幻觉口径），其余保留 4 位小数。"""
    return "<0.001" if p < 0.001 else f"{p:.4f}"


def normality_test(file_path: str | None = None, column: str | None = None, method: str = "auto",
                   inline_data: list | dict | None = None) -> dict:
    """正态性检验（Shapiro-Wilk / D'Agostino-Pearson），输出统计量、p、偏度、峰度。"""
    try:
        # D17 连锁 optional 化的运行期强校验（SPEC §12.6）
        require_non_none(column=column)
        if method not in _METHODS:
            raise DataLabError("method 仅支持 auto/shapiro/dagostino", EC.PARAM)
        df, data_source = resolve_data(file_path, inline_data)
        if column not in df.columns:
            raise DataLabError(f"缺少必需列: {column}；实际列: {list(df.columns)}", EC.COLUMN_MISSING)
        if not pd.api.types.is_numeric_dtype(df[column]):
            raise DataLabError(f"列 {column} 不是数值列，无法做正态检验", EC.COLUMN_TYPE)
        x = df[column].dropna().to_numpy(dtype=float)
        n = int(x.size)
        if n < SHAPIRO_MIN_N:
            raise DataLabError(f"至少需要 3 个有效值，当前 {n}", EC.INSUFFICIENT)
        if float(x.std(ddof=1)) == 0:
            raise DataLabError(f"列 {column} 为常数列（方差为 0），正态检验无意义", EC.STRUCTURE)

        method_used = "shapiro" if (method == "auto" and n <= SHAPIRO_MAX_N) else (
            "dagostino" if method == "auto" else method)
        if method_used == "shapiro" and n > SHAPIRO_MAX_N:
            raise DataLabError(f"样本量 {n} 超出 Shapiro 适用范围（3~5000），"
                               f"请改用 method=dagostino 或抽样", EC.SCALE)
        if method_used == "dagostino" and n > DAGOSTINO_MAX_N:
            raise DataLabError(f"样本过大（{n} 行），请随机抽样后重试", EC.SCALE)
        if method_used == "dagostino" and n < DAGOSTINO_MIN_N:
            raise DataLabError(f"D'Agostino 检验要求样本量 >=8，当前 {n}，请用 method=shapiro", EC.INSUFFICIENT)

        if method_used == "shapiro":
            stat, p = sps.shapiro(x)
            name = "Shapiro-Wilk"
        else:
            stat, p = sps.normaltest(x)
            name = "D'Agostino-Pearson"
        stat, p = float(stat), float(p)
        skew = float(sps.skew(x, bias=False))
        kurtosis = float(sps.kurtosis(x, fisher=True, bias=False))
        normal = bool(p > ALPHA)

        result = {
            "method_used": method_used, "n": n, "statistic": stat, "p_value": p,
            "skew": skew, "kurtosis": kurtosis, "normal": normal,
            "threshold_alpha": ALPHA,
        }
        if normal:
            summary = (f"{name} 检验：p={p:.4f} ≥α=0.05，不能拒绝正态假设（数据近似正态）；"
                       f"偏度 {skew:.2f}、峰度 {kurtosis:.2f}")
        else:
            summary = (f"{name} 检验：p={_fmt_p(p)} <α=0.05，拒绝正态假设（数据明显非正态）；"
                       f"偏度 {skew:.2f}、峰度 {kurtosis:.2f}，建议改用 nonparametric_test")
        _payload = ok(result, summary)
        _payload["data_source"] = data_source
        return _payload
    except DataLabError as e:
        return err(e.code, str(e))
    except Exception:
        return err(EC.CALC, "计算失败，请检查数据内容与参数设置（详见服务端日志）")


def register(mcp) -> None:
    """注册到 MCPServer（mcp 2.x，工具名 = 函数名）。"""
    mcp.add_tool(normality_test, description=__import__("sys").modules[__name__].__doc__)

