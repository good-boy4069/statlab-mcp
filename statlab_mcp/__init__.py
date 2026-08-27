r"""statlab_mcp 包初始化。

BLAS 单线程默认值（红队 P2-12）：必须先于 numpy 首次导入执行——若等到
timeseries_backtest_forecast 模块级再 setdefault，OpenBLAS/MKL 已随 numpy
初始化完成，环境变量不再生效，auto_arima 数值归约顺序不受控、逐字节确定性
承诺失效。仅在用户未显式预设时补默认（setdefault 语义，显式配置优先）。
"""
import os as _os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")
