# worker コンテナ用 Dockerfile。
#
# 設計指針:
# - api と同じ uv ベースのマルチステージ
# - メール / PDF パース extras を含める
# - 監視・バッチ用ツール（cron / tini 等）は将来必要になり次第追加

# ── builder stage ──
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# lxml は wheel が無い環境でビルドが必要なため build-essential を入れる。
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock /app/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --extra mail --extra pdf --extra llm

COPY src /app/src
COPY worker /app/worker
# README.md は pyproject.toml の readme フィールドが参照するため必須。
COPY README.md /app/README.md
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra mail --extra pdf --extra llm

# ── runtime stage ──
FROM python:3.12-slim AS runtime

# lxml の実行時に必要な共有ライブラリだけ runtime に入れる（軽量化）。
RUN apt-get update \
    && apt-get install -y --no-install-recommends libxml2 libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 kakeibo \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash kakeibo

WORKDIR /app

COPY --from=builder --chown=kakeibo:kakeibo /opt/venv /opt/venv
COPY --from=builder --chown=kakeibo:kakeibo /app /app

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER kakeibo

# heartbeat ファイルは /tmp 配下を既定とする。kakeibo ユーザでも書込み可能。
# 上書きは環境変数 WORKER_HEARTBEAT_PATH で行う。
ENV WORKER_HEARTBEAT_PATH=/tmp/worker_heartbeat

# Phase 0 では heartbeat を更新するだけの idle ループを回す。
# Phase 2.x で取込ジョブのスケジューラに置換する。
CMD ["python", "-m", "kakeibo.worker"]

# heartbeat ファイルの mtime が 120 秒以内であれば healthy 判定。
# busybox の stat は -c フォーマット指定がないため Python で実装する。
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,sys,time; p=os.environ.get('WORKER_HEARTBEAT_PATH','/tmp/worker_heartbeat'); sys.exit(0 if os.path.exists(p) and (time.time()-os.path.getmtime(p))<120 else 1)" || exit 1
