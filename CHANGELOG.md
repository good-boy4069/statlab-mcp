# 变更日志

本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)。所有重大变更均记录于此。

## [v1.0.2] - 2026-08-26

### 修复（Qoder 锐评 v1.0.1 轮）
- **协议一致性闭合**：NaN/Inf/类型错误等被 pydantic schema 层拦截的参数，此前由 MCP SDK
  以英文 `Error executing tool ... validation error` 文本返回；现由 `StatlabServer` 子类
  转换为统一的 `{status:"error", message:"参数校验失败：..."}` 中文 JSON，
  与工具内错误格式闭环（锐评 #1）。仅转换参数校验失败场景，其余 ToolError 原样透传，
  与 SDK 分类逻辑对齐（UnexpectedToolError 不误标为参数问题）。
- **mu0 防御补全**：`hypothesis_test` 的 `mu0` 参数此前无有限性校验（NaN/Inf 会污染
  t 统计量与 CI 输出），现拒绝并中文报错。

### 新增
- `requirements.min.txt`：纯 stdio 最小直接依赖裁剪版（锐评 #2 建议，SPEC 第 7 节预告兑现）。
- `tests/test_protocol_errors.py`：协议层错误中文化的 stdio 集成回归测试（3 个用例）。
- `.github/ISSUE_TEMPLATE/`：Bug 报告与功能请求模板；`CHANGELOG.md` 本文档。

### 其他
- README 测试数量口径统一为当前实测值（此前 223/233 并存）。

## [v1.0.1] - 2026-08-26

### 修复（首份外部锐评："锐评报告"全部 17 项）
- **P0**：月/季/年频时序数据 100% 失效（非固定频率 `.nanos` 抛异常/误判超限）——
  改为锚点实测步长，月频 forecast/trend/decompose/anomaly 全链路可用；
  趋势分析对头部缺失数据输出错误结论（kendalltau 遇 NaN 被改写为"无趋势"，
  summary 拼 "nan"）——dropna 后检验并报告 `head_dropped`。
- **P1（M1-M8）**：日内数据按天聚合如实说明；非季节数据不再误标 SARIMA；
  cluster/PCA 含 NaN 数值列 listwise 剔除并报告；cliff_delta 常量组不再误拒
  （负值效应按 |v| 判档并修正档位循环语义）；anomaly_detect 说明书同步 std 判据、
  iqr 不再打印无效 threshold；相关矩阵校正对数用实际可计算对数；卡方常量数值列
  友好中文报错。
- **P2（L1-L10 及工程）**：死代码清理；Welch df 保留小数；配对 mean1/mean2 语义；
  plot_box 补 min/max；plot_scatter 英文分支；趋势斜率恰为 0 不再误报方向；
  簇样本量单位；server 模块级注册（import 启动方式同样注册 25 工具）；
  describe 重复列名如实注明；10+ 测试盲区用例补齐；测试卫生清理
  （tmp_path/绝对路径/死分支）；pywin32 环境标记；Python 版本统一 3.11+；
  图片归档 30 天清理；outlier_detect 数值列上限 200；Linux 中文图降级漏网修复。

### 新增
- GitHub Actions CI：Windows/Ubuntu × Python 3.11/3.13（pytest + ruff + stdio 冒烟）。
- `requirements.txt` 锁定 pytest-cov/ruff；SPEC 增补（Web 栈知情披露、最低版本口径）。

### 红队复检轮
- 独立红队子代理逐项复检 + 重新攻击：确认无 P0/P1/中残留；修复其新发现的
  GBK 表头误报、尾部 NaN 外推、PCA 单样本、CI 镜像四项轻级问题。

## [v1.0.0] - 2026-08-26

### 初始发布
- 25 个纯计算统计工具（数据探查 5 / 统计推断 6 / 建模 5 / 时序 4 / 可视化 5）
  + auto_analysis 编排层方案（文档交付物）。
- 统一协议：`{status:"ok", result, summary}` / `{status:"error", message}`；
  图片顶层 `__image__`；确定性（seed=42，两次运行逐字节一致）。
- 安全防护：仅本地路径（拒绝 UNC/NUL）、50MB/200 万行/500MB 上限、
  xlsx zip 炸弹预检、JSON 20MB 放大防护、异常输出截断、错误中文脱敏。
- 中文全链路：GBK 回退、中文字体图表（无字体降级英文）、中文错误消息。
- 文档：SPEC（协议与统计口径）+ 8 份设计文档 + 客户端接入配置。
- 锁定依赖（requirements.txt 全量 pip freeze）+ 223 个 pytest + ruff + stdio 冒烟。