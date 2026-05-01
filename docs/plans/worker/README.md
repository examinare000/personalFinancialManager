---
title: worker サービス Phase1 タスク指示書
service: worker
phase: 1
status: Ready
parent_index: docs/plans/10-phase1-overview.md
last_updated: 2026-05-01
---

# worker サービス Phase1 タスク指示書

`compose.yml` の `worker` サービスに帰属する Phase1 タスク群（1.2〜1.8）。Phase1 の **アプリケーションロジックの大部分** がこのサービスに集約される。

## サービス境界（このディレクトリで扱うもの）

| 範囲 | パス |
|---|---|
| ドメイン共通型（Transaction / Holding / BalanceSnapshot / `compute_hash`） | `src/kakeibo/domain/` |
| 取込アダプタ抽象基底 | `src/kakeibo/adapters/base.py`, `errors.py` |
| MUFG / SMBC CSV 機関別アダプタ | `src/kakeibo/adapters/mufg.py`, `smbc.py` |
| 取込 CLI（`python -m kakeibo.ingest`） | `src/kakeibo/ingest/cli.py`, `registry.py`, `persister.py` |
| 月次サマリ SQL のクエリファイルとアプリ層ランナー | `sql/queries/monthly_summary.sql`, `src/kakeibo/sql/runner.py` |
| ハッシュ冪等性 property-based test | `tests/unit/domain/test_hash.py`, `test_hash_boundary.py` |
| 取込パイプライン全般のユニットテスト | `tests/unit/{domain,adapters,ingest,sql}/` |

実行時は `worker` コンテナ（`worker/Dockerfile` が `src/kakeibo` を COPY）の `python -m kakeibo.ingest <institution> <path>` などから起動する。Phase 2.1 で watchdog Watcher に発展する基盤。

### このディレクトリでは扱わないもの

| 対象 | 帰属サービス |
|---|---|
| Alembic マイグレーション本体 | `postgres` サービス（`docs/plans/postgres/`） |
| Flask REST API | `api` サービス（Phase 0 完了済み、Phase 3.1 で本格着手） |
| Next.js UI | `ui` サービス（Phase 3.2 から） |

## タスク一覧

| 連番 | 担当タスク | 指示書 | 原典プラン | ブランチ | 優先度 |
|---|---|---|---|---|---|
| 01 | Phase 1.2 ドメイン共通型 | [`01-domain-types.md`](./01-domain-types.md) | `docs/plans/03-phase1-domain-types.md` | `feature/domain-types` | 🔴 高 |
| 02 | Phase 1.3 IngestAdapter ABC | [`02-ingest-adapter-base.md`](./02-ingest-adapter-base.md) | `docs/plans/04-phase1-ingest-adapter-base.md` | `feature/ingest-adapter-base` | 🔴 高 |
| 03 | Phase 1.4 MUFG CSV アダプタ | [`03-mufg-csv-adapter.md`](./03-mufg-csv-adapter.md) | `docs/plans/05-phase1-mufg-csv-adapter.md` | `feature/adapter-mufg-csv` | 🟡 中 |
| 04 | Phase 1.5 SMBC CSV アダプタ | [`04-smbc-csv-adapter.md`](./04-smbc-csv-adapter.md) | `docs/plans/06-phase1-smbc-csv-adapter.md` | `feature/adapter-smbc-csv` | 🟡 中 |
| 05 | Phase 1.6 取込CLI | [`05-ingest-cli.md`](./05-ingest-cli.md) | `docs/plans/07-phase1-ingest-cli.md` | `feature/ingest-cli` | 🔴 高 |
| 06 | Phase 1.7 ハッシュ冪等性テスト強化 | [`06-hash-idempotency-tests.md`](./06-hash-idempotency-tests.md) | `docs/plans/08-phase1-hash-idempotency-tests.md` | `feature/hash-idempotency-tests` | 🟡 中 |
| 07 | Phase 1.8 月次サマリ SQL | [`07-monthly-summary-sql.md`](./07-monthly-summary-sql.md) | `docs/plans/09-phase1-monthly-summary-sql.md` | `feature/monthly-summary-sql` | 🟡 中 |

## 実行順序（推奨直列）

`docs/plans/10-phase1-overview.md` §3 と整合：

```
[postgres/01]
   ↓
worker/01 (1.2) → worker/02 (1.3) ┬─→ worker/03 (1.4) ┐
                                  └─→ worker/04 (1.5) ┴─→ worker/05 (1.6)
                                                              ├─→ worker/06 (1.7)
                                                              └─→ worker/07 (1.8)
```

並行可能ペア：
- `worker/03 (1.4 MUFG)` と `worker/04 (1.5 SMBC)` は独立 → 別 Worker 並列起動可
- `worker/06 (1.7)` と `worker/07 (1.8)` は CLI 完了後に独立並列可

## 共通の前提

- Python 3.12 / `pyproject.toml` の `[project.dependencies]` を使用。`click`, `httpx`, `pydantic`, `psycopg`, `sqlalchemy`, `structlog` はインストール済み。
- 開発依存（dev extras）に `pytest`, `hypothesis`, `testcontainers`, `pyright`, `ruff` 宣言済み。
- 取込パイプラインは **dataclass + Raw SQL** を基本（`agent-rules/01-claude-behavior.md` のシンプルさ優先方針、`docs/plans/03-phase1-domain-types.md` §実装方針 1 「pydantic を入れない」）。
- `compute_hash` は `src/kakeibo/domain/transaction.py` に実装し、機関別アダプタは **再実装禁止**（`docs/plans/05-phase1-mufg-csv-adapter.md` §実装方針 7）。

## 担当 Worker サブエージェント（モードB前提）

`agent-rules/91-claude-subagent-coding.md` に従い、メインClaudeはオーケストレーターに徹する。

| Worker | 主な責務 |
|---|---|
| Planner | 各タスクの実装範囲確認、影響ファイル列挙、ADR との整合確認 |
| Coder | テスト先行 → 最小実装 → リファクタ。各タスクごとに 1 ブランチ・複数コミット |
| Reviewer | アダプタ間の独立性、`compute_hash` の決定性、CLI 終了コード規約、`ON CONFLICT` の冪等性、SQL の境界条件 |
| Git-composer | `agent-rules/10-git-strategy.md` 準拠のアトミックコミット、`feature/*` ブランチ運用 |

並列実行ポリシー: `worker/03` と `worker/04` は同一メッセージ内で 2 体の Coder を並列起動可。

## 共通の品質ゲート

各タスク完了時：

```bash
pytest tests/unit/                   # 該当範囲が全件緑（10 秒以内）
ruff check .                         # 違反ゼロ
pyright                              # 警告ゼロ
```

統合確認（`worker/05` 完了後）：
- 実 Postgres（testcontainers）に対して取込 CLI が成功
- 同一 CSV 2 回投入で行数増えず（Phase1 完了条件 (b)）
- `worker/07` 完了後、月次サマリ SQL が手計算と一致（完了条件 (c)）

## Phase1 完了条件カバレッジ

| 完了条件（`docs/plans/01-development-plan.md` §3.1） | 担当タスク |
|---|---|
| (a) `alembic upgrade head` 冪等 | `postgres/01` |
| (b) 同一 CSV 2 回投入で行数増えず | `worker/05` + `worker/06` |
| (c) 月次サマリ SQL が手計算と一致 | `worker/07` |
| (d) 全ユニットテスト緑、`pyright` クリーン | 全タスク横断 |
