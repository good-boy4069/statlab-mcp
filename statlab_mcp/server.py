"""statlab-mcp MCP Server 入口（规范 9：只注册工具 + to_jsonable，保持 ≤150 行）。

Windows 硬性要求 1：stdio 用 UTF-8 编码输出中文 JSON（配合 $env:PYTHONUTF8="1"，
双保险：stdout 流重配置为 utf-8）。
注册机制（红队裁决 I4）：每个工具模块提供一个 register(mcp) 回调，本文件仅逐模块
收集注册，每工具一行；任何统计计算都发生在 tools/ 下各工具模块，本文件不含逻辑。
协议一致性（Qoder 锐评 #1）：pydantic 参数校验失败（NaN/Inf/类型错误等）默认由 SDK
以英文 is_error 文本返回，StatlabServer 子类将其转换为统一的 {status:"error",...} JSON，
与工具内错误格式闭环。
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from mcp.server.mcpserver import MCPServer  # mcp 2.x：FastMCP 重构后的高层服务器类
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp_types import CallToolResult, TextContent  # mcp 2.x：类型定义在 mcp_types 包
from pydantic import ValidationError

from statlab_mcp import _imaging, _resources
from statlab_mcp.tools import (
    _common,  # 导入即执行 seed(42)/Agg/字体/日志配置；EC 错误码常量亦经此引用
)

# 包版本（P2-A 自安装冒烟要求 initialize 上报与发布一致的版本字符串）
try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _pkg_version

    _PKG_VERSION = _pkg_version("statlab-mcp")
except PackageNotFoundError:                          # 源码直跑（未安装）时兜底
    _PKG_VERSION = "0+dev"
from statlab_mcp.tools import data_exploration_correlation_matrix as _t4  # 工具 4
from statlab_mcp.tools import data_exploration_data_type_check as _t2  # 工具 2
from statlab_mcp.tools import data_exploration_describe_statistics as _t1  # 工具 1
from statlab_mcp.tools import data_exploration_impute_missing as _t28  # 工具 28（v1.2.0）
from statlab_mcp.tools import data_exploration_missing_report as _t3  # 工具 3
from statlab_mcp.tools import data_exploration_outlier_detect as _t5  # 工具 5
from statlab_mcp.tools import inference_anova_test as _t7  # 工具 7
from statlab_mcp.tools import inference_chi_square_test as _t8  # 工具 8
from statlab_mcp.tools import inference_confidence_interval as _t10  # 工具 10
from statlab_mcp.tools import inference_effect_size as _t11  # 工具 11
from statlab_mcp.tools import inference_hypothesis_test as _t6  # 工具 6
from statlab_mcp.tools import inference_nonparametric_test as _t26  # 工具 26
from statlab_mcp.tools import inference_normality_test as _t9  # 工具 9
from statlab_mcp.tools import inference_power_analysis as _t27  # 工具 27（v1.1.0）
from statlab_mcp.tools import modeling_cluster_analysis as _t14  # 工具 14
from statlab_mcp.tools import modeling_feature_importance as _t16  # 工具 16
from statlab_mcp.tools import modeling_linear_regression as _t12  # 工具 12
from statlab_mcp.tools import modeling_logistic_regression as _t13  # 工具 13
from statlab_mcp.tools import modeling_pca_analysis as _t15  # 工具 15
from statlab_mcp.tools import timeseries_anomaly_detect as _t20  # 工具 20
from statlab_mcp.tools import timeseries_backtest_forecast as _t29  # 工具 29（v1.2.0）
from statlab_mcp.tools import timeseries_seasonal_decompose as _t18  # 工具 18
from statlab_mcp.tools import timeseries_time_series_forecast as _t17  # 工具 17
from statlab_mcp.tools import timeseries_trend_analysis as _t19  # 工具 19
from statlab_mcp.tools import visualization_plot_box as _t25  # 工具 25
from statlab_mcp.tools import visualization_plot_forecast as _t24  # 工具 24
from statlab_mcp.tools import visualization_plot_heatmap as _t23  # 工具 23
from statlab_mcp.tools import visualization_plot_histogram as _t22  # 工具 22
from statlab_mcp.tools import visualization_plot_scatter as _t21  # 工具 21

# 工具模块注册表：随实现推进逐个加入（每工具一行）
_TOOL_MODULES: list = [_t1, _t2, _t3, _t4, _t5, _t6, _t9, _t10, _t7, _t8, _t11,
                       _t12, _t13, _t14, _t15, _t16, _t17, _t18, _t19, _t20,
                       _t21, _t22, _t23, _t24, _t25, _t26, _t27, _t28, _t29]

# 工具数：29（v1.2.0 开发中）
_PARAM_HINT = "参数校验失败：请检查参数类型与取值范围（拒绝 NaN/Inf 等非法数值）"
# v1.1.0：错误结构新增机器可读 error_code（E1001=参数校验失败，SPEC 第 9 节）
_PARAM_HINT_JSON = json.dumps({"status": "error", "error_code": _common.EC.PARAM,
                               "message": _PARAM_HINT}, ensure_ascii=False)


class StatlabServer(MCPServer):
    """协议一致性子类（v1.1.0 起两职责）：

    1. pydantic 参数校验失败转统一中文错误 JSON（Qoder 锐评 #1）——SDK 默认以英文
       is_error 文本返回，此处仅转换参数校验失败场景并注入 error_code=E1001；
    2. STATLAB_DESC_MODE=slim 时 tools/list 的 description 切换为参数摘要
       （P0-1 双轨开关，进程启动时解析一次；默认 full 与 v1.0.3 逐字节一致）。
    """

    async def call_tool(self, name, arguments, context=None):
        try:
            result = await super().call_tool(name, arguments, context)
        except ToolError as e:
            # 与 SDK _handle_call_tool 的分类逻辑对齐：仅普通 ToolError（且根因是参数
            # ValidationError）属于"参数校验失败"；UnexpectedToolError（工具内部意外
            # 异常）与其余 ToolError 原样透传，避免工具内部库抛出的 ValidationError
            # 被误标为参数问题。
            if not isinstance(e, UnexpectedToolError) and isinstance(e.__cause__, ValidationError):
                return CallToolResult(
                    content=[TextContent(type="text", text=_PARAM_HINT_JSON)],
                    is_error=True)
            raise
        if IMAGE_MODE == "content":
            # v1.1.0 P0-3 图片双轨（SPEC 第 5 节）：仅带图成功结果被改写为内容块列表，
            # 其余结果原样透传；默认 path 模式完全不介入。
            result = _imaging.rewrite_for_content_mode(result)
        return result

    def add_tool(self, fn, name=None, **kwargs):
        if DESC_MODE == "slim" and kwargs.get("description"):
            kwargs["description"] = _resources.make_slim_description(
                fn, kwargs["description"])
        return super().add_tool(fn, name=name, **kwargs)


mcp = StatlabServer("statlab-mcp", version=_PKG_VERSION)

# 进程启动解析一次（stderr 中文告警后回退默认值由 _resources/_imaging 负责）
DESC_MODE = _resources.resolve_desc_mode()
IMAGE_MODE = _imaging.resolve_image_mode()


def bootstrap(mcp_server: MCPServer) -> None:
    """注册全部工具与静态 resources（27 = 工具数 + statlab://spec，随 P1-3 变 28）。"""
    for mod in _TOOL_MODULES:
        mod.register(mcp_server)
    _resources.register_resources(mcp_server, _TOOL_MODULES)


def _register_all() -> None:
    """调用各工具模块的 register(mcp) 完成工具注册。"""
    bootstrap(mcp)


# 模块级执行（外部评审 L9）：无论 `python -m statlab_mcp.server` 直跑，还是被 import
# 的启动方式（第三方托管器 import 本模块后调 run），全部工具与 resources 都会注册。
_register_all()

def main() -> None:
    """console 入口（PyPI 发布后 `statlab-mcp` 命令 / `uvx statlab-mcp` 直接启动 stdio 服务器）。"""
    mcp.run()


if __name__ == "__main__":
    main()
