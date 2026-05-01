---
title: postgres サービス 実装プラン索引
service: postgres
status: Ready
parent_index: docs/plans/10-phase1-overview.md
last_updated: 2026-05-01
---

# postgres サービス 実装プラン索引

`compose.yml` の `postgres` サービス（PostgreSQL 16-alpine 公式イメージ + Alembic マイグレーション資産）に帰属する Phase 別タスク指示書の索引。ADR-014 によりサービス専有プランは `<service>/docs/plans/PhN/` に集約される。

## サービス境界（このサービスで扱うもの）

- `postgres/src/alembic/versions/*.py` のマイグレーションスクリプト（= `postgres` コンテナのスキーマ正本）
- `postgres/src/sql/queries/*.sql` の共通 SQL（月次サマリ等）
- スキーマ存在検証・冪等性検証の pytest（`postgres/tests/`、移行先）
- ENUM・CHECK・UNIQUE 等の制約定義
- ドメイン型（dataclass / enum）の定義（`shared/kakeibo_shared/domain/`）— DB スキーマと一体運用するため postgres プランで管理

### このサービスで扱わないもの

| 対象 | 帰属サービス |
|---|---|
| 取込アダプタ / 取込 CLI / メールパーサ | `worker` サービス（`worker/docs/plans/`） |
| 月次サマリ SQL のアプリ層ランナー | `worker` サービス |
| Flask `/health` エンドポイント | `api` サービス（Phase 0 で完了済み） |
| Next.js UI | `ui` サービス |

実行コンテナは `postgres` だが、Alembic 自体は Python ランタイムを持つ `worker` コンテナから `compose.yml` の `./postgres/src/alembic` 読取マウント経由で実行する（ADR-014）。スキーマの **正本** は postgres 帰属、**実行主体** は worker という関係。

## Phase 別タスク

### Phase 1（→ `Ph1/`）

| 連番 | タスク | 指示書 | ブランチ | 優先度 |
|---|---|---|---|---|
| 02 | Phase 1.1 DBスキーマ・マイグレーション基盤 | [`Ph1/02-db-schema-and-migrations.md`](./Ph1/02-db-schema-and-migrations.md) | `feature/db-schema-initial` | 🔴 高 |
| 03 | Phase 1.2 ドメイン共通型 | [`Ph1/03-domain-types.md`](./Ph1/03-domain-types.md) | `feature/domain-types` | 🔴 高 |
| 09 | Phase 1.8 月次サマリ SQL | [`Ph1/09-monthly-summary-sql.md`](./Ph1/09-monthly-summary-sql.md) | `feature/monthly-summary-sql` | 🟡 中 |

連番 04〜08（アダプタ・CLI・冪等性テスト）は `worker/docs/plans/Ph1/` に帰属。

### Phase 2（→ `Ph2/`）

[`Ph2/README.md`](./Ph2/README.md)。Phase 2 では postgres スキーマ拡張なし。Phase 4 LLM 分類着手時に `Ph4/` を新設してカテゴリ拡張等を扱う。

### Phase 3（→ `Ph3/`）

[`Ph3/README.md`](./Ph3/README.md)。Phase 3 でも postgres スキーマ拡張なし。

## 実行順序

`postgres` サービスのタスクは Phase1 の **最上流**（`docs/plans/10-phase1-overview.md` §3 の直列上流）。`worker` サービス側のすべてのタスクが `postgres/Ph1/02` の完了を起点とする。

```
postgres/Ph1/02 → postgres/Ph1/03 ┬─→ worker/Ph1/04 → worker/Ph1/05 ↘
                                  └─→ worker/Ph1/06 → worker/Ph1/07 → worker/Ph1/08
                                                                    → postgres/Ph1/09
```

## 前提

- `compose.yml` `postgres` サービスは `Dockerfile` を持たず、`postgres:16-alpine` 公式イメージそのまま使用
- secret は `./secrets/pg_password.txt`（運用上は配置済前提）
- Alembic 設定（`postgres/src/alembic.ini` / `postgres/src/alembic/env.py`）は Phase 0 で配備済み。`resolve_database_url()` は環境変数 `DATABASE_URL` から接続文字列を解決する
- マイグレーション作業時は `worker` コンテナ内（`compose.yml` で `./postgres/src/alembic` をマウント）、または開発ホストの venv から `alembic -c postgres/src/alembic.ini upgrade head` を実行する

## 担当 Worker サブエージェント（モードB前提）

`agent-rules/91-claude-subagent-coding.md` に従い、メインClaudeはオーケストレーターに徹し、以下を起動する：

| Worker | 役割 |
|---|---|
| Planner | マイグレーション 5 ファイル分割の確定、`information_schema` クエリ仕様の起案 |
| Coder | テスト先行（`test_schema.py` / `test_migration_idempotency.py`）→ Alembic versions 実装 |
| Reviewer | ADR-004/005/006 と DDL の整合、CHECK 制約の網羅性、冪等性 |
| Git-composer | `feature/db-schema-initial` でアトミックコミット 5 件以上（テスト先行 → 各 versions ファイル → ヘルパ） |
