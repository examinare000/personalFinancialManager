# ui コンテナ用 Dockerfile（Phase 0 スタブ）。
#
# 設計指針:
# - Phase 3.x までは静的 HTML を nginx で配信する最小実装にとどめる。
# - Phase 3.1 で React + Vite に置換する際、本ファイルは multi-stage の
#   `builder` ステージ追加のみで本番イメージ化できる構成にしておく。
# - 3000 番ポートで listen し、Caddy（ui:3000 へ reverse_proxy）と整合する。
# - HEALTHCHECK は wget で同ポートを叩く（alpine の busybox に同梱）。

FROM nginx:1.27-alpine

# 非 root 実行は将来のフェーズで導入する（nginx 公式イメージは
# 起動時に root でのバインドが必要なため、Phase 0 ではデフォルトの
# root 起動を維持する）。
#
# 設計判断: agent-rules/70-docker-environments.md は非 root 推奨だが、
# nginx alpine の挙動安定性を優先し Phase 3 移行時に再検討する旨を
# 申し送りに記載する。

# 既定の default.conf を上書き。3000 番に listen するための最小設定。
COPY ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY ui/index.html /usr/share/nginx/html/index.html

EXPOSE 3000

# Phase 0 のヘルスチェックは静的 HTML が返ることを確認するだけで十分。
# alpine の busybox には wget が同梱されているため curl は不要。
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/ || exit 1
