# statlab-mcp —— 统计分析 MCP Server 容器镜像（stdio 服务器）
# 构建：docker build -t statlab-mcp:1.0.3 .
# 运行（stdio 需与客户端共享进程，通常经 docker run + 客户端 exec 或 compose stdin/stdout 直连）：
#   docker run --rm -i statlab-mcp:1.0.3
# 镜像体积说明：科学计算栈（numpy/scipy/pandas/matplotlib/pmdarima）约 1-2GB，属预期。

FROM python:3.13-slim

ENV PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 中文字体（matplotlib 无字体时降级英文；此处提供 Noto CJK 使中文图表可用）
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用层缓存）
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt --timeout 120

# 再装包本体（含 console script：statlab-mcp）
COPY . .
RUN python -m pip install .

# stdio 服务器：容器必须通过 stdin/stdout 与 MCP 客户端通信（docker run -i）
CMD ["python", "-m", "statlab_mcp.server"]