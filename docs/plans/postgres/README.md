---
title: postgres サービス Phase1 タスク指示書
service: postgres
phase: 1
status: Ready
parent_index: docs/plans/10-phase1-overview.md
last_updated: 2026-05-01
---

# postgres サービス Phase1 タスク指示書

`compose.yml` の `postgres` サービス（PostgreSQL 16-alpine 単一コンテナ + Alembic マイグレーション本体）に紐づく Phase1 タスクをまとめる。原典プランは `docs/plans/02-phase1-db-schema-and-migrations.md`。

## サービス境界（このディレクトリで扱うもの）

- `alembic/versions/*.py` のマイグレーションスクリプト（=`postgres` コンテナのスキーマ正本）
- スキーマ存在検証・冪等性検証の pytest（`tests/unit/db/`）
- ENUM・CHECK・UNIQUE 等の制約定義
- `src/kakeibo/db/` の最小ヘルパ（マイグレーションテストで再利用される engine factory のみ）

### このディレクトリでは扱わないもの

| 対象 | 帰属サービス |
|---|---|
| ドメイン型 / アダプタ / 取込CLI | `worker` サービス（`docs/plans/worker/`） |
| 月次サマリ SQL のクエリ本体・ランナー | `worker` サービス（`docs/plans/worker/07-monthly-summary-sql.md`） |
| Flask `/health` エンドポイント | `api` サービス（Phase 0 で完了済み） |
| Next.js UI | `ui` サービス（Phase1 では着手なし） |

実行コンテナは `postgres` だが、Alembic 自体は `worker` コンテナまたは開発ホストから `alembic upgrade head` を叩く運用（`compose.yml` の worker は `src/` を持っている）。スキーマの **正本** が `postgres` 帰属であって、実行主体は worker という関係。

## タスク一覧

| 連番 | 担当タスク | 指示書 | 原典プラン | ブランチ | 優先度 |
|---|---|---|---|---|---|
| 01 | Phase 1.1 DBスキーマ・マイグレーション基盤 | [`01-schema-migrations.md`](./01-schema-migrations.md) | `docs/plans/02-phase1-db-schema-and-migrations.md` | `feature/db-schema-initial` | 🔴 高 |

## 実行順序

`postgres` サービスのタスクは Phase1 の **最上流**（`docs/plans/10-phase1-overview.md` §3 の直列上流）。`worker` サービス側のすべてのタスクが本タスク完了を起点とする。

```
postgres/01 → worker/01 → worker/02 → worker/03 ↘
                                    → worker/04 → worker/05 → worker/06
                                                            → worker/07
```

## 前提

- `compose.yml` `postgres` サービスは `Dockerfile` を持たず、`postgres:16-alpine` 公式イメージそのまま使用。
- secret は `./secrets/pg_password.txt`（既に運用上は配置済前提）。
- Alembic 設定（`alembic.ini` / `alembic/env.py`）は Phase 0 で配備済み。`resolve_database_url()` は環境変数 `DATABASE_URL` から接続文字列を解決する。
- マイグレーション作業時は `worker` コンテナ内、または開発ホストの venv から `alembic upgrade head` を実行する。

## 担当 Worker サブエージェント（モードB前提）

`agent-rules/91-claude-subagent-coding.md` に従い、メインClaudeはオーケストレーターに徹し、以下を起動する：

| Worker | 役割 |
|---|---|
| Planner | マイグレーション 5 ファイル分割の確定、`information_schema` クエリ仕様の起案 |
| Coder | テスト先行（`test_schema.py` / `test_migration_idempotency.py`）→ Alembic versions 実装 |
| Reviewer | ADR-004/005/006 と DDL の整合、CHECK 制約の網羅性、冪等性 |
| Git-composer | `feature/db-schema-initial` でアトミックコミット 5 件以上（テスト先行 → 各 versions ファイル → ヘルパ） |
