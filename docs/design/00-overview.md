---
title: システム全体俯瞰と設計ドキュメント索引
version: 1.0
status: Draft
last_updated: 2026-05-01
related_adrs: []
---

# 0. システム全体俯瞰

個人向け資産・家計管理アプリ（kakeibo）の全コンポーネント間関係と、
設計ドキュメントの所在を一覧する索引。詳細はリンク先を参照。

## 1. コンポーネント概観

| コンポーネント | 役割 | コードルート |
|---|---|---|
| postgres | データの正本（取引・残高・ルール・カテゴリ） | `postgres/`（Phase 0 で配備済。マイグレーション本体は Phase 1.1 で着手） |
| worker | 取込・分類・連動取引・出力連携バッチ | `worker/` |
| api | 集計エンドポイント（Flask、Phase 3） | `api/` |
| ui | ダッシュボード（Next.js、Phase 3.2） | `ui/` |
| caddy | リバースプロキシ・Tailscale 認証 | （ルート設定のみ） |
| backup | dump/restic | （ルート設定のみ） |

## 2. 設計ドキュメント索引

### 2.1 横断・俯瞰（root `docs/design/`）

- `04-deployment-stack.md` — compose / network / Caddy / backup の全体構成
- `05-security-model.md` — 脅威モデル・シークレット運用（全サービス横断）

### 2.2 サービス専有 design

- postgres: `../../postgres/docs/design/README.md`
  - `01-data-model.md`
- worker: `../../worker/docs/design/README.md`
  - `02-ingest-adapters.md` / `03-categorization-engine.md` / `06-reconciler.md` / `07-output-integrations.md` / `08-ingest-flow.md`
- api: `../../api/docs/design/README.md`（現状専有 design なし、Phase 3 以降）
- ui: `../../ui/docs/design/README.md`（現状専有 design なし、Phase 4 以降）

## 3. 関連リソース

- 実装計画: `../plans/01-development-plan.md`
- 意思決定記録: `../adr/`
