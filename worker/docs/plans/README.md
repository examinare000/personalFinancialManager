---
title: worker サービス 実装プラン索引
service: worker
status: Ready
parent_index: docs/plans/10-phase1-overview.md
last_updated: 2026-05-01
---

# worker サービス 実装プラン索引

`compose.yml` の `worker` サービスに帰属する Phase 別タスク指示書の索引。ADR-014 によりサービス専有プランは `<service>/docs/plans/PhN/` に集約される。

## サービス境界（このサービスで扱うもの）

| 範囲 | パス |
|---|---|
| ドメイン共通型（Transaction / Holding / BalanceSnapshot / `compute_hash`） | `shared/kakeibo_shared/domain/` |
| 取込アダプタ抽象基底 | `worker/src/kakeibo_worker/adapters/base.py`, `errors.py` |
| MUFG / SMBC CSV 機関別アダプタ | `worker/src/kakeibo_worker/adapters/mufg.py`, `smbc.py` |
| 取込 CLI（`python -m kakeibo_worker.ingest`） | `worker/src/kakeibo_worker/ingest/cli.py`, `registry.py`, `persister.py` |
| 取込パイプライン全般のユニットテスト | `worker/tests/unit/{domain,adapters,ingest}/` |
| watchdog Watcher / メールパーサ / PayPal API（Phase 2） | `worker/src/kakeibo_worker/` |
| LLM カテゴリ分類（Phase 4） | `worker/src/kakeibo_worker/categorization/` |

実行時は `worker` コンテナ（`worker/Dockerfile` が `worker/src` と `shared/` を COPY）の `python -m kakeibo_worker.ingest <institution> <path>` などから起動する。

### このサービスで扱わないもの

| 対象 | 帰属サービス |
|---|---|
| Alembic マイグレーション本体 / 月次サマリ SQL | `postgres` サービス（`postgres/docs/plans/`） |
| Flask REST API | `api` サービス（Phase 0 完了済み、Phase 3.1 で本格着手） |
| Next.js UI | `ui` サービス（Phase 3.2 から） |

## Phase 別タスク

### Phase 1（→ `Ph1/`）

| 連番 | タスク | 指示書 | ブランチ | 優先度 |
|---|---|---|---|---|
| 04 | Phase 1.3 IngestAdapter ABC | [`Ph1/04-ingest-adapter-base.md`](./Ph1/04-ingest-adapter-base.md) | `feature/ingest-adapter-base` | 🔴 高 |
| 05 | Phase 1.4 MUFG CSV アダプタ | [`Ph1/05-mufg-csv-adapter.md`](./Ph1/05-mufg-csv-adapter.md) | `feature/adapter-mufg-csv` | 🟡 中 |
| 06 | Phase 1.5 SMBC CSV アダプタ | [`Ph1/06-smbc-csv-adapter.md`](./Ph1/06-smbc-csv-adapter.md) | `feature/adapter-smbc-csv` | 🟡 中 |
| 07 | Phase 1.6 取込CLI | [`Ph1/07-ingest-cli.md`](./Ph1/07-ingest-cli.md) | `feature/ingest-cli` | 🔴 高 |
| 08 | Phase 1.7 ハッシュ冪等性テスト強化 | [`Ph1/08-hash-idempotency-tests.md`](./Ph1/08-hash-idempotency-tests.md) | `feature/hash-idempotency-tests` | 🟡 中 |

連番 02 / 03（DBスキーマ／ドメイン型）と 09（月次サマリ SQL）は `postgres/docs/plans/Ph1/` に帰属。

### Phase 2（→ `Ph2/`）

[`Ph2/README.md`](./Ph2/README.md) に詳細索引。watchdog Watcher、メールパーサ、PayPal API アダプタ、cron バッチランナー等の 8 タスク。

### Phase 3（→ `Ph3/`）

[`Ph3/README.md`](./Ph3/README.md)。worker サービスは Phase 3 で実装変更を持たない（ロジックは `api` / `ui` 主体）。Phase 4 LLM 分類着手時に `Ph4/` を新設する。

## 実行順序（Phase 1 推奨直列）

`docs/plans/10-phase1-overview.md` §3 と整合：

```
[postgres/Ph1/02 → postgres/Ph1/03]
   ↓
worker/Ph1/04 ┬─→ worker/Ph1/05 ┐
              └─→ worker/Ph1/06 ┴─→ worker/Ph1/07
                                       ├─→ worker/Ph1/08
                                       └─→ postgres/Ph1/09
```

並行可能ペア：
- `worker/Ph1/05 (MUFG)` と `worker/Ph1/06 (SMBC)` は独立 → 別 Coder 並列起動可
- `worker/Ph1/08` と `postgres/Ph1/09` は CLI 完了後に独立並列可

## 共通の前提

- Python 3.12 / `pyproject.toml` の `[project.dependencies]` を使用
- 取込パイプラインは **dataclass + Raw SQL** を基本（`postgres/docs/plans/Ph1/03-domain-types.md` §実装方針 1 「pydantic を入れない」）
- `compute_hash` は `shared/kakeibo_shared/domain/transaction.py` に実装し、機関別アダプタは **再実装禁止**（`worker/docs/plans/Ph1/05-mufg-csv-adapter.md` §実装方針 7）

## 共通の品質ゲート

各タスク完了時：

```bash
docker compose run --rm worker pytest worker/tests/   # 該当範囲が全件緑
docker compose run --rm worker ruff check .           # 違反ゼロ
docker compose run --rm worker pyright                # 警告ゼロ
```

統合確認（`worker/Ph1/07` 完了後）：
- 実 Postgres（testcontainers）に対して取込 CLI が成功
- 同一 CSV 2 回投入で行数増えず（Phase1 完了条件 (b)）
- `postgres/Ph1/09` 完了後、月次サマリ SQL が手計算と一致（完了条件 (c)）
