# worker コンテナ用 Dockerfile（ADR-015 / ADR-014）。
#
# 設計指針:
# - api と同じ uv ベースのマルチステージ構成（ADR-015）
# - 依存マニフェストは shared/pyproject.toml に集約。本 image では
#   ``--extra worker --extra mail --extra pdf --extra llm --extra dev`` で
#   alembic / メール / PDF / LLM / 開発ツールを導入する。
# - dev extras を含むため worker は **テスト・lint・typecheck の実行基盤** にもなる
#   （ADR-015 §開発者ワークフロー）。
# - 監視・バッチ用ツール（cron / tini 等）は将来必要になり次第追加。

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

# 依存解決のキャッシュ層: pyproject + lock のみ先に COPY する。
# shared/uv.lock は universal lock のため、worker は必要な extras を全選択する。
COPY shared/pyproject.toml shared/uv.lock /app/shared/

WORKDIR /app/shared
# worker は dev / 横断テスト基盤も兼ねるため、api 専有依存（flask）も含めて
# install する。これにより worker コンテナから api 由来のテスト
# （`api/tests/test_app.py` など）も実行できる（ADR-015）。
# worker 本番イメージに flask が混入するが、Phase 0 での簡素さを優先する。
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project \
        --extra api --extra worker \
        --extra mail --extra pdf --extra llm --extra dev

# ── ソース配信 ──
WORKDIR /app
# shared モジュール群（PYTHONPATH 経由で配信、パッケージとしては install しない）
COPY shared/kakeibo_shared /app/shared/kakeibo_shared
# worker サービス専有コード
COPY worker/src /app/worker/src

# ── runtime stage ──
FROM python:3.12-slim AS runtime

# 実行時に必要な共有ライブラリ。
# - libxml2 / libxslt1.1: lxml（メールパーサ）
# - libatomic1: pyright が内蔵 nodeenv で取得する prebuilt node が
#   libatomic.so.1 を要求する（dev extras に同梱、ADR-015 で worker は
#   テスト・lint・typecheck の実行基盤を兼ねるため必須）。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libxml2 libxslt1.1 libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# docker CLI + docker compose plugin を持ち込む（ADR-015 §テストの所在）。
# tests/ に compose 構文検証テスト群があり、worker コンテナから
# `docker compose config` を叩けるようにするため。
# Docker daemon は /var/run/docker.sock の bind mount で host のものを再利用する
# （compose.override.yml で設定）。
COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker:27-cli /usr/local/libexec/docker/cli-plugins/docker-compose \
                          /usr/local/libexec/docker/cli-plugins/docker-compose

RUN groupadd --gid 1000 kakeibo \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash kakeibo

WORKDIR /app

COPY --from=builder --chown=kakeibo:kakeibo /opt/venv /opt/venv
COPY --from=builder --chown=kakeibo:kakeibo /app /app

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/shared:/app/worker/src"

USER kakeibo

# heartbeat ファイルは /tmp 配下を既定とする。kakeibo ユーザでも書込み可能。
# 上書きは環境変数 WORKER_HEARTBEAT_PATH で行う。
ENV WORKER_HEARTBEAT_PATH=/tmp/worker_heartbeat

# Phase 0 では heartbeat を更新するだけの idle ループを回す。
# Phase 2.x で取込ジョブのスケジューラに置換する。
CMD ["python", "-m", "kakeibo_worker"]

# heartbeat ファイルの mtime が 120 秒以内であれば healthy 判定。
# busybox の stat は -c フォーマット指定がないため Python で実装する。
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,sys,time; p=os.environ.get('WORKER_HEARTBEAT_PATH','/tmp/worker_heartbeat'); sys.exit(0 if os.path.exists(p) and (time.time()-os.path.getmtime(p))<120 else 1)" || exit 1
