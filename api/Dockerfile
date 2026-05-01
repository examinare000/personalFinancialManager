# api コンテナ用 Dockerfile（ADR-015 / ADR-014）。
#
# 設計指針:
# - build context はリポジトリルート（compose.yml の context: . を参照）。
#   shared/ と api/src/ の両者を COPY するために必須。
# - uv はホストにインストールせず、本 Dockerfile 内で公式 uv image から
#   バイナリのみ取得して使う（ADR-015）。
# - 依存マニフェストは shared/pyproject.toml に集約され、shared/uv.lock で
#   全 extras を universal lock している（ADR-015）。
#   本 image は ``--extra api`` で flask + 共通依存だけを導入する。
# - shared/kakeibo_shared/ は素のモジュール群（ADR-014 Q1=案B）。
#   COPY 後に PYTHONPATH へ加えて配信する（uv install の対象にはしない）。
# - マルチステージで本番 image から build 用ツールを排除。
# - 非 root ユーザで実行（agent-rules/70-docker-environments.md）。

# ── builder stage ──
FROM python:3.12-slim AS builder

# uv 公式 distroless image から uv バイナリだけ取得する。
# ホストへの uv インストールは不要（ADR-015）。
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# 依存解決のキャッシュ層: pyproject + lock のみ先に COPY する。
# shared/uv.lock は universal lock のため、本 image では --extra api だけ選ぶ。
COPY shared/pyproject.toml shared/uv.lock /app/shared/

WORKDIR /app/shared
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --extra api

# ── ソース配信 ──
WORKDIR /app
# shared モジュール群（PYTHONPATH 経由で配信、パッケージとしては install しない）
COPY shared/kakeibo_shared /app/shared/kakeibo_shared
# api サービス専有コード
COPY api/src /app/api/src

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
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/shared:/app/api/src"

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
