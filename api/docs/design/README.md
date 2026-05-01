# api サービス 設計ドキュメント

## 現状
api サービス専有の詳細設計は **存在しない**。Phase 3 以降で追加予定。

Phase 3 実装計画は `../../../docs/plans/api/Ph3/README.md`（別ブランチで追加予定）を参照。

## 横断設計（root）
- `../../../docs/design/00-overview.md`
- `../../../docs/design/04-deployment-stack.md`（api は Caddy 配下に配置）
- `../../../docs/design/05-security-model.md`（Tailscale 認証ヘッダ伝播）

## 参照する他サービス設計
- postgres データモデル: `../../../postgres/docs/design/01-data-model.md`
- worker 分類エンジン（API レスポンス整合用）: `../../../worker/docs/design/03-categorization-engine.md`
