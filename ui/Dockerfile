# ui コンテナ用 Dockerfile（Next.js 14+ App Router / standalone build）。
#
# 設計指針:
# - build context はリポジトリルート（compose.yml の context: . と整合）
# - Next.js standalone 出力を runtime ステージに最小限だけ持ち込み、
#   本番イメージから node_modules / src をすべて排除する
# - 非 root ユーザで実行（agent-rules/70-docker-environments.md 必須）
# - 3000 番ポートで listen し、Caddy（ui:3000 へ reverse_proxy）と整合する
# - HEALTHCHECK は Node 内蔵 http で叩く（node:20-alpine には wget/curl がない）
#
# 参照パターン: api/Dockerfile:14-73（builder→runtime / 非 root / urllib HEALTHCHECK）

# ── builder stage ──
FROM node:20-alpine AS builder

WORKDIR /app

# 依存解決のためのファイルだけ先に COPY し、レイヤキャッシュを最大化する
# （api/Dockerfile が pyproject.toml/uv.lock を先に COPY するのと同じ思想）。
# package-lock.json は決定2に従いリポジトリへ commit 済みのため必須扱い
# （欠落時は build を fail させて運用上で気付ける方が望ましい）。
COPY ui/package.json ui/package-lock.json /app/

RUN npm ci

# アプリ本体（src ディレクトリと next 設定）を COPY して build 実行。
# ADR-014: App Router のソースは ``ui/src/app`` 配下に配置する。
# Next.js は src/app と app の両方を自動検出するため設定変更は不要。
COPY ui/next.config.mjs ui/tsconfig.json /app/
COPY ui/src /app/src

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── runtime stage ──
FROM node:20-alpine AS runtime

# node:20-alpine には UID/GID 1000 の `node` 非 root ユーザが既に存在する。
# 独自ユーザを作ると `gid '1000' in use` で build が失敗するため、
# ベースイメージ提供のユーザをそのまま流用する（再現性確認: docker run --rm node:20-alpine id node）。

WORKDIR /app

# Next.js standalone 出力を持ち込む。.next/standalone は必要な
# node_modules 部分だけを含み、.next/static / public は別途コピーする。
COPY --from=builder --chown=node:node /app/.next/standalone /app
COPY --from=builder --chown=node:node /app/.next/static /app/.next/static

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

USER node

EXPOSE 3000

# server.js は standalone 出力に含まれる Next.js の起動スクリプト。
CMD ["node", "server.js"]

# node:20-alpine には wget / curl がないため、Node 内蔵 http で /
# を叩いて 200 を確認する。失敗時は exit 1 を返して HEALTHCHECK を失敗扱いにする
# （api/Dockerfile の urllib プローブと同じ思想）。
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/', (r) => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))" || exit 1
