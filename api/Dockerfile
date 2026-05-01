# api コンテナ用 Dockerfile。
#
# 設計指針:
# - build context はリポジトリルート（compose.yml の context: . を参照）
#   ADR-014 により共有コードは ``shared/`` 配下にあるため、build context は
#   引き続きルートを採用し ``shared/`` と ``api/src/`` の両者を COPY する。
# - uv をベースイメージに導入し、pyproject.toml + uv.lock から依存をインストール
# - マルチステージで本番イメージから build 用ツールを排除
# - 非 root ユーザで実行（agent-rules/70-docker-environments.md）
#
# 実装メモ:
# - サービス専有コード: ``api/src/kakeibo_api/`` （Flask アプリ本体）
# - 共有コード: ``shared/kakeibo_shared/`` （config / logging / db / domain）
# - 開発時は compose.override.yml が ``./api/src`` ``./shared`` を bind mount する

# ── builder stage ──
FROM python:3.12-slim AS builder

# uv 公式 distroless イメージから uv バイナリだけ取得する。
# astral-sh/uv の README が推奨する手法で、最小依存で uv を導入できる。
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# 依存解決のためのファイルだけ先に COPY し、レイヤキャッシュを最大化する。
COPY pyproject.toml uv.lock /app/

# 本番では dev / pdf / mail / llm extras は基本的に不要。
# Phase 進行に応じて --extra を追加して再ビルドする。
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# アプリ本体を COPY して editable インストール。
# README.md は pyproject.toml の readme フィールドが参照するため必須。
# api/src は kakeibo_api パッケージ、shared は kakeibo_shared パッケージ。
COPY api/src /app/src
COPY shared /app/shared
COPY README.md /app/README.md
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# ── runtime stage ──
FROM python:3.12-slim AS runtime

# 非 root ユーザを作成。GID/UID は Synology DSM のデフォルト範囲に近い 1000 を採用。
RUN groupadd --gid 1000 kakeibo \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash kakeibo

WORKDIR /app

# ビルド済み venv とアプリコードを必要分だけ持ち込む。
COPY --from=builder --chown=kakeibo:kakeibo /opt/venv /opt/venv
COPY --from=builder --chown=kakeibo:kakeibo /app /app

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER kakeibo

EXPOSE 8000

# Phase 0 では Werkzeug 開発サーバ（kakeibo_api.__main__）で起動する。
# Phase 3.x で gunicorn / uvicorn に切替える際は本 CMD のみ更新する。
# - 0.0.0.0 バインドは external ネットワーク内（ui/caddy）からの接続用。
# - host バインドは compose.override.yml で 127.0.0.1 に絞る。
CMD ["python", "-m", "kakeibo_api"]

# python:3.12-slim には curl/wget が無いため、urllib で /health を叩く。
# 200 以外でステータス 1 を返し、HEALTHCHECK を失敗扱いにする。
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; r=urllib.request.urlopen('http://localhost:8000/health',timeout=3); sys.exit(0 if r.status==200 else 1)" || exit 1
