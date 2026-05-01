---
title: postgres/01 DBスキーマ・マイグレーション基盤
service: postgres
phase_task_id: 1.1
priority: 高
source_plan: docs/plans/02-phase1-db-schema-and-migrations.md
branch: feature/db-schema-initial
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# postgres/01 DBスキーマ・マイグレーション基盤（Phase 1.1）

## このファイルの位置付け

原典プラン `docs/plans/02-phase1-db-schema-and-migrations.md` をサブエージェントが指示書 1 枚で着手できる形に再編した、`postgres` サービス担当の **実装タスクシート**。原典は変更しない。本指示書と原典で内容が乖離した場合は **原典を優先** する（`docs/plans/01-development-plan.md` §1.4 改版方針）。

## 担当サービス

`compose.yml` `postgres` サービス（PostgreSQL 16-alpine）。Alembic マイグレーションの **スキーマ正本** が本タスクで確定する。実行は `worker` コンテナまたは開発ホストの venv から `alembic upgrade head`。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流（依存） | なし（Phase1 起点） |
| 下流（本タスクが解放） | `worker/01-domain-types.md` 以降のすべて |

`docs/plans/10-phase1-overview.md` §4 のクリティカルパス起点。

## 入力（Coder が読むべきファイル）

1. **原典プラン**: `docs/plans/02-phase1-db-schema-and-migrations.md`（必読・全文）
2. **DDL 定義**: `docs/plans/00-initial-design.md` §4.2
3. **データモデル**: `postgres/docs/design/01-data-model.md`
4. **関連 ADR**: `docs/adr/004-postgres-jsonb.md` / `005-numeric-money-type.md` / `006-hash-uniqueness.md`
5. **Alembic 既存資産**: `alembic.ini`, `alembic/env.py`（再初期化禁止。`target_metadata` は Phase1 では `None` 維持）
6. **既存テストユーティリティ**: `tests/_compose_utils.py`（テスト用 Postgres 起動）
7. **依存宣言**: `pyproject.toml` `[project.optional-dependencies].dev` の `testcontainers`

## 期待される出力ファイル

| パス | 区分 | 役割 |
|---|---|---|
| `alembic/versions/0001_create_institutions_and_accounts.py` | 新規 | 機関・口座テーブル |
| `alembic/versions/0002_create_categories.py` | 新規 | カテゴリ階層 |
| `alembic/versions/0003_create_transactions.py` | 新規 | 取引テーブル + `hash` UNIQUE + `category_source` ENUM |
| `alembic/versions/0004_create_holdings_and_snapshots.py` | 新規 | 保有銘柄・残高スナップショット |
| `alembic/versions/0005_create_categorization_rules.py` | 新規 | カテゴリルール |
| `tests/unit/db/__init__.py` | 新規 | テストパッケージ初期化 |
| `tests/unit/db/conftest.py` | 新規（任意） | 一時 Postgres コンテナの session-scope fixture |
| `tests/unit/db/test_schema.py` | 新規 | 7 テーブル・主要カラム型・UNIQUE・ENUM の存在検証 |
| `tests/unit/db/test_migration_idempotency.py` | 新規 | 2 回連続 `alembic upgrade head` が no-op |
| `src/kakeibo/db/__init__.py` | 既存（追記） | テスト共有用 engine factory のエクスポート（既存 `session.py` を再利用） |

`alembic/env.py` の改修は **必要時のみ**（`target_metadata` を bind したくなった場合）。Phase1 では Raw SQL ベースで進めるため、原則は `None` のまま。

## 実装手順（TDD: Red → Green → Refactor）

### 0. ブランチ作成

```bash
git checkout develop && git pull origin develop
git checkout -b feature/db-schema-initial
```

### 1. Red: テストを先に書く

1. `tests/unit/db/test_schema.py` に「7 テーブル存在 / `transactions.amount` が NUMERIC(18,4) / `transactions.hash` UNIQUE / `category_source` ENUM 値が `('rule','llm','manual')`」の検証を `information_schema` ベースで記述。
2. `tests/unit/db/test_migration_idempotency.py` に「`alembic upgrade head` を 2 回連続実行して `transactions` 行数が 0 のまま、テーブル数も同一」の検証を記述。
3. `tests/unit/db/conftest.py` で `testcontainers.postgres.PostgresContainer` を session-scope で立ち上げ、`DATABASE_URL` を注入する fixture を提供。
4. `pytest tests/unit/db/` を流して **全件落ちる** ことを確認。

### 2. Green: マイグレーションを 5 分割で追加

各 versions ファイルは **1 ファイル = 1 コミット**。`down_revision` を線形に連結する。

| ファイル | 主要 DDL |
|---|---|
| `0001_*` | `institutions`, `accounts` |
| `0002_*` | `categories`（自己参照 FK 含む） |
| `0003_*` | `category_source` ENUM 作成 → `transactions`（`amount NUMERIC(18,4) NOT NULL`, `hash CHAR(64) NOT NULL UNIQUE`, `raw_payload JSONB DEFAULT '{}'`） |
| `0004_*` | `holdings`, `balance_snapshots`（同日同口座 UNIQUE） |
| `0005_*` | `categorization_rules` |

各ファイル追加ごとに対応する pytest ケースが緑になることを確認しながら進める。

### 3. Refactor

- ENUM 作成・削除を `_create_category_source_enum(op)` のような共通ヘルパに抽出可能なら抽出（同一マイグレーション内のみ）。
- マイグレーション間で重複する制約名命名規約（`ix_<table>_<col>` / `uq_<table>_<col>`）を確定。

## 受入条件（コミット前にすべて緑）

- `alembic upgrade head` が空 DB に対して成功する
- `alembic upgrade head` を 2 回連続実行して 2 回目が no-op で成功する
- `pytest tests/unit/db/` が全件緑（10 秒以内）
- `transactions.amount` に文字列を投入すると PostgreSQL の型エラーで弾かれる
- `transactions.hash` への重複 INSERT が `psycopg.errors.UniqueViolation`
- `category_source` ENUM に範囲外値を投入すると例外
- `pyright` クリーン、`ruff check` 違反ゼロ

## 品質ゲート（`agent-rules/00-core-principles.md` コミット前ユニバーサルチェック）

```bash
pytest tests/unit/db/        # 全件緑
ruff check .                 # 違反ゼロ
pyright                      # 警告ゼロ
```

## ブランチ・コミット規約

- ブランチ: `feature/db-schema-initial`（`develop` 起点）
- コミット粒度（最低 6 件、`agent-rules/10-git-strategy.md` 準拠）：
  1. `テスト: スキーマ存在・冪等性検証テストを先行作成`
  2. `機能: 機関・口座テーブルのマイグレーション追加`
  3. `機能: カテゴリ階層テーブルのマイグレーション追加`
  4. `機能: 取引テーブルとhash UNIQUE制約・category_source ENUMを追加`
  5. `機能: 保有銘柄・残高スナップショットテーブルのマイグレーション追加`
  6. `機能: カテゴリルールテーブルのマイグレーション追加`
- 各メッセージは日本語 1〜2 文・WHY 優先。
- マージは `develop` への fast-forward。

## 完了報告テンプレ（Coder → メイン）

```markdown
## 実施内容
Phase 1.1 DBスキーマ・マイグレーション基盤を実装。

## 成果物
- alembic/versions/0001_*.py 〜 0005_*.py
- tests/unit/db/test_schema.py / test_migration_idempotency.py / conftest.py

## 検証結果
- pytest tests/unit/db/: 全件緑（X 秒）
- alembic upgrade head 2 回実行: 冪等成功
- pyright / ruff: クリーン

## 既知の課題・申し送り
（あれば）

## 次のアクション提案
worker/01-domain-types.md（Phase 1.2）の着手準備が整った。
```

## 注意事項

- 既存の `alembic/`・`alembic.ini`・`alembic/env.py` を **再初期化禁止**（`alembic init` を打たない）。
- `pytest-postgresql` は dev 依存に未宣言。**`testcontainers` を使用** する（pyproject.toml で宣言済み）。
- ENUM のダウン側で型もドロップする。
- `target_metadata` は Phase1 では `None` 維持（SQLAlchemy ORM は Phase 1.2 では使わず、共通型は dataclass で実装）。
