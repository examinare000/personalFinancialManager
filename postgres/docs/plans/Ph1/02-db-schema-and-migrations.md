---
title: Phase 1.1 DBスキーマ・マイグレーション基盤
phase: 1
task_id: 1.1
status: Draft
priority: 高
parent: docs/plans/01-development-plan.md
last_updated: 2026-04-30
---

# Phase 1.1 DBスキーマ・マイグレーション基盤

## タスク概要

`docs/plans/00-initial-design.md` §4.2 の DDL を Alembic マイグレーションへ落とし込み、PostgreSQL 16 上で **冪等に適用できる初期スキーマ基盤**を整備する。Phase1 のすべての後続タスク（共通型、アダプタ、取込CLI、月次サマリ SQL）が依存する土台であり、Phase1 完了条件 (a)「`alembic upgrade head` が冪等に実行できる」を直接満たす。

参照: `docs/plans/01-development-plan.md` §4.1 Phase 1.1, §3.1 完了条件 (a), `postgres/docs/design/01-data-model.md`。

## 目的・背景

### 目的

- 初期設計書 §4.2 が定義する 7 テーブル（`institutions` / `accounts` / `categories` / `transactions` / `holdings` / `balance_snapshots` / `categorization_rules`）を Alembic で管理可能なスキーマとして実装する。
- 取引の冪等性を保証する `transactions.hash` の UNIQUE 制約と、金額の厳密表現を保証する NUMERIC 型を、最初のマイグレーションから正しく組み込む。
- 後続のアダプタ・CLI・SQL クエリが「スキーマは確定済み」という前提で実装に集中できる状態を作る。

### 背景

- Phase1 のすべてのタスクが本タスク完了を起点として進行するため、最上流のクリティカルパス上にある（`01-development-plan.md` §5）。
- 関連 ADR は ADR-004（PostgreSQL 16 + JSONB）, ADR-005（NUMERIC 型採用）, ADR-006（hash UNIQUE） の 3 本で、いずれも本タスクの実装で初めて具体化される。
- マイグレーションの粒度は「institutions / accounts」「categories」「transactions」「holdings / balance_snapshots」「categorization_rules」の 5 ファイルに分割し、1 PR 内で 5 コミットに分けて履歴をたどりやすくする（`01-development-plan.md` §4.1 補足）。

## スコープ

### 含む

- 既存 Alembic 設定（`postgres/src/alembic.ini`, `postgres/src/alembic/env.py` は実装済み・`script_location = alembic`）への versions 追加。
- 7 テーブルの初期スキーマ migration 一式（5 ファイル分割）を `postgres/src/alembic/versions/` 配下に追加。
- `transactions.hash` の UNIQUE インデックス、`amount` の NUMERIC 型と CHECK 制約、`category_source` ENUM の制約定義。
- マイグレーションの冪等性検証（2 回連続適用が無害である）。
- スキーマ存在検証用ユニットテストフィクスチャ（dev 依存に宣言済みの `testcontainers` を用いてテスト用 Postgres コンテナを起動、または既存 `tests/_compose_utils.py` で読み込む `docker-compose.test.yml` 経由で利用）。

### 含まない

- アプリ層の ORM モデル（dataclass / pydantic は Phase 1.2 で扱う）。
- データ投入用 CLI / アダプタ（Phase 1.3〜1.6）。
- ダウングレード（`alembic downgrade`）の実運用検証（Phase 4 のリリース時に総合確認）。
- バックアップ / リストア手順（ADR-012, Phase 4）。

## 依存タスク

- なし（Phase1 最上流タスク。`docs/plans/01-development-plan.md` §5 のクリティカルパス起点）。

## 後続タスク

- `03-phase1-domain-types.md`（Phase 1.2 共通型: 本タスクのスキーマに対応する dataclass を定義）。
- `04-phase1-ingest-adapter-base.md`（Phase 1.3 IngestAdapter ABC: 共通型を介して間接依存）。
- `09-phase1-monthly-summary-sql.md`（Phase 1.8 月次サマリ SQL: `transactions` テーブル定義に依存）。

## 対象ファイル/モジュール

| パス | 区分 | 役割 |
|---|---|---|
| `postgres/src/alembic.ini` | 既存・参照のみ | Alembic 設定。`script_location = alembic`、`sqlalchemy.url = ${DATABASE_URL}` プレースホルダ。本タスクでは原則変更しない |
| `postgres/src/alembic/env.py` | 既存・参照のみ | マイグレーション実行コンテキスト。`resolve_database_url()` 実装済。`target_metadata` を本タスクで bind するなら必要に応じて改修 |
| `postgres/src/alembic/versions/0001_create_institutions_and_accounts.py` | 新規 | 機関・口座テーブル |
| `postgres/src/alembic/versions/0002_create_categories.py` | 新規 | カテゴリ階層 |
| `postgres/src/alembic/versions/0003_create_transactions.py` | 新規 | 取引テーブル + `hash` UNIQUE |
| `postgres/src/alembic/versions/0004_create_holdings_and_snapshots.py` | 新規 | 保有銘柄・残高スナップショット |
| `postgres/src/alembic/versions/0005_create_categorization_rules.py` | 新規 | カテゴリルール |
| `shared/kakeibo_shared/db/__init__.py` | 新規 | DB 接続ヘルパ（テスト用エンジン共有） |
| `tests/unit/db/test_schema.py` | 新規 | 全テーブル・全制約の存在検証 |
| `tests/unit/db/test_migration_idempotency.py` | 新規 | 冪等性検証 |

実装段階で具体ファイル名・分割は微調整可（マイグレーション粒度 5 分割は固定）。既存 `postgres/src/alembic/`・`postgres/src/alembic.ini`・`postgres/src/alembic/env.py` を再初期化（`alembic init`）してはならない。

## 実装方針

1. **Alembic versions の追加**: 既存の `postgres/src/alembic/`・`postgres/src/alembic.ini`・`postgres/src/alembic/env.py` を再初期化せず、`postgres/src/alembic/versions/` 配下に新規リビジョンファイルを追加する。`env.py` は `resolve_database_url()` で `DATABASE_URL` を解決済みのため再実装しない。`target_metadata` は Phase1 では SQLAlchemy ORM を使わず Raw SQL ベースであるため `None` のまま運用する（必要になった段階で `kakeibo.db.models.metadata` を bind する形に拡張）。
2. **マイグレーション 5 ファイル分割**: 各ファイルに `op.create_table(...)` と `op.create_index(...)` を記述。`down_revision` を明示的に連結し、線形履歴を保つ。
3. **`amount` NUMERIC**: ADR-005 に従い `sa.Numeric(18, 4)`（整数部 14 桁 + 小数 4 桁）で定義。CHECK 制約で `amount IS NOT NULL` を強制。
4. **`transactions.hash` UNIQUE**: ADR-006 に従い `CHAR(64)`（SHA256 hex）で定義し `unique=True`。NULL を許容しない。
5. **`category_source` ENUM**: PostgreSQL ENUM 型として `('rule', 'llm', 'manual')` を作成（`postgresql.ENUM`）。マイグレーションのダウン側で型もドロップ。
6. **JSONB**: `transactions.raw_payload` は `JSONB` 型（ADR-004）。NULL 可、デフォルト `'{}'::jsonb`。
7. **冪等性**: Alembic は同じ revision に対し 2 回目の `upgrade head` を no-op として扱うため、1 回目成功後 2 回目を実行してもエラーが出ないことを統合テストで確認する。
8. **テスト用 Postgres**: ユニットテストでは dev 依存に宣言済みの `testcontainers`（pyproject.toml `[project.optional-dependencies].dev` 参照）でテスト用 Postgres コンテナを立ち上げる、または既存 `tests/_compose_utils.py` ユーティリティ経由で `docker-compose.test.yml` を起動する。テストごとに一時 DB を作成→マイグレーション適用→検証→破棄。`pytest-postgresql` は dev 依存に未宣言のため採用しない。

## 受入条件

- `alembic upgrade head` が空 DB に対して成功する。
- `alembic upgrade head` を 2 回連続で実行しても 2 回目が no-op として成功する（冪等）。
- `pytest tests/unit/db/test_schema.py` が以下を緑で検証する。
  - 7 テーブルすべての存在。
  - 各テーブルの主要カラム（`amount`, `hash`, `category_source`, `raw_payload` 等）の型と NULL 制約。
  - `transactions.hash` の UNIQUE インデックス存在。
  - `category_source` ENUM の許容値が `('rule', 'llm', 'manual')` のみ。
- `transactions.amount` に文字列・NaN を投入すると、PostgreSQL の型エラーで弾かれる。
- 同一 `transactions.hash` の 2 回目の INSERT が UNIQUE 違反例外になる。
- `pyright` クリーン、`ruff` 違反なし。

## テスト計画

### ユニットテスト（テスト先行）

1. **スキーマ存在検証**: `information_schema.tables` / `information_schema.columns` を SQL で読み出し、期待スキーマ（テストフィクスチャに JSON で定義）と一致するかを検証する。
2. **制約違反検証**: NUMERIC への文字列投入、`hash` 重複 INSERT、`category_source` 範囲外値投入が、それぞれ期待される `psycopg.errors.*` 例外を発生させることを確認する。
3. **冪等性検証**: マイグレーション適用済み DB に対する `alembic upgrade head` 再実行が成功し、テーブル数・行数が変化しないことを確認する。

### 品質ゲート

- ユニットテスト全件 10 秒以内で緑（`agent-rules/11-testing-strategy.md`）。
- `pyright` 警告ゼロ、`ruff check` 違反ゼロ。

### TDD アプローチ

- Red: マイグレーションを書く前に `test_schema.py` の検証ロジックを書き、期待スキーマと実 DB が一致しないため落ちることを確認。
- Green: 5 ファイルのマイグレーションを順に追加し、各段階で対応するテストが緑になることを確認。
- Refactor: マイグレーションヘルパ（共通の ENUM 作成関数等）を抽出。

## 想定 issue タイトル / ブランチ名

- 想定 issue タイトル: `Phase 1.1: DBスキーマ・マイグレーション基盤の整備`
- ブランチ名: `feature/db-schema-initial`
- ベースブランチ: `develop`
- マージ戦略: fast-forward（`agent-rules/10-git-strategy.md` 準拠）
