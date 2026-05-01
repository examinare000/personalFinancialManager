---
title: Phase1 サービス別タスク振り分けインデックス
phase: 1
status: Ready
parent: docs/plans/10-phase1-overview.md
last_updated: 2026-05-01
---

# Phase1 サービス別タスク振り分けインデックス

`docs/plans/10-phase1-overview.md`（Phase1 全体俯瞰）と `docs/plans/01-development-plan.md` §4.1（タスク詳細）を、`compose.yml` のサービス（コンテナ）単位に振り分けたディスパッチテーブル。各サービスごとのサブディレクトリにある指示書（Coder / Planner サブエージェントが直接参照する実装タスクシート）の入口。

## 1. サービス × Phase1 タスク マトリクス

`compose.yml` のサービス名で振り分け。`postgres`（DB）と `worker`（取込パイプライン）に責務を集約し、`api`/`ui` は Phase1 では新規タスクなし。

| サービス | Phase 1.1 | 1.2 | 1.3 | 1.4 | 1.5 | 1.6 | 1.7 | 1.8 | 担当数 |
|---|---|---|---|---|---|---|---|---|---|
| `postgres` | ● | – | – | – | – | – | – | – | 1 |
| `worker` | – | ● | ● | ● | ● | ● | ● | ● | 7 |
| `api` | – | – | – | – | – | – | – | – | 0 |
| `ui` | – | – | – | – | – | – | – | – | 0 |

`postgres` は **スキーマ正本**（Alembic migrations）を持つコンテナ。`worker` はそれを使うアプリケーション層全般を担う。

## 2. サブディレクトリ構成

```
docs/plans/
├── 10-phase1-overview.md           # Phase1 全体俯瞰（既存）
├── 11-phase1-service-assignments.md # 本ファイル（サービス振り分け）
├── postgres/
│   ├── README.md                    # postgres サービス Phase1 一覧
│   └── 01-schema-migrations.md      # Phase 1.1 (源: 02-phase1-...md)
├── worker/
│   ├── README.md                    # worker サービス Phase1 一覧
│   ├── 01-domain-types.md           # Phase 1.2 (源: 03-phase1-...md)
│   ├── 02-ingest-adapter-base.md    # Phase 1.3 (源: 04-phase1-...md)
│   ├── 03-mufg-csv-adapter.md       # Phase 1.4 (源: 05-phase1-...md)
│   ├── 04-smbc-csv-adapter.md       # Phase 1.5 (源: 06-phase1-...md)
│   ├── 05-ingest-cli.md             # Phase 1.6 (源: 07-phase1-...md)
│   ├── 06-hash-idempotency-tests.md # Phase 1.7 (源: 08-phase1-...md)
│   └── 07-monthly-summary-sql.md    # Phase 1.8 (源: 09-phase1-...md)
├── api/
│   └── README.md                    # Phase1 担当タスクなし宣言
└── ui/
    └── README.md                    # Phase1 担当タスクなし宣言
```

各サービスサブディレクトリの指示書は **原典プラン（`docs/plans/02〜09-phase1-*.md`）の翻案** であり、原典は変更しない。原典との乖離時は **原典優先**（`docs/plans/01-development-plan.md` §1.4）。

## 3. 現在の実装状況スナップショット（2026-05-01 時点）

`docs/plans/02〜09` の 8 タスクは **すべて未着手**。既に存在するのは Phase 0 のインフラ：

| 完了済（Phase 0） | パス |
|---|---|
| Docker Compose 構成 | `compose.yml`, `compose.override.yml`, `Caddyfile` |
| Postgres コンテナ | `compose.yml` `postgres` サービス（`postgres:16-alpine`） |
| Worker heartbeat ループ | `src/kakeibo/worker/main.py`, `worker/Dockerfile` |
| API ヘルスチェック | `src/kakeibo/api/app.py` `/health`, `api/Dockerfile` |
| UI 雛形 | `ui/app/{layout,page}.tsx`, `ui/Dockerfile` |
| 設定ローダー | `src/kakeibo/config.py`, `src/kakeibo/logging.py` |
| Alembic 設定 | `alembic.ini`, `alembic/env.py`（versions は空） |
| DB セッション骨格 | `src/kakeibo/db/session.py` |
| Phase1 計画文書 | `docs/plans/02〜10` |
| 計画文書の構造検証テスト | `tests/unit/test_phase1_plan_documents.py` |

Phase1 のドメインロジック（`src/kakeibo/domain/`, `src/kakeibo/adapters/`, `src/kakeibo/ingest/`）は **すべて namespace package のプレースホルダ** のみで、実装は本タスクシート群でこれから着手する。

## 4. 推奨実装フロー（モードB: Claude単体サブエージェント協調）

`agent-rules/91-claude-subagent-coding.md` に従い、メインClaudeはオーケストレーターに徹する。実装フローは `docs/plans/10-phase1-overview.md` §3 を踏襲：

```
1. postgres/01           （Planner → Coder → Reviewer → Git-composer）
2. worker/01            （同上）
3. worker/02            （同上）
4. worker/03 ‖ worker/04（Coder 2 体並列起動可能）
5. worker/05            （同上）
6. worker/06 ‖ worker/07（並列可能）
```

各タスクは 1 ブランチ・1 PR 単位（`agent-rules/10-git-strategy.md`）。コミットはアトミックに分割し、コミットメッセージは日本語 1〜2 文（`機能:` / `修正:` / `テスト:` / `文書:` 等）。

## 5. Phase1 完了条件カバレッジ

`docs/plans/01-development-plan.md` §3.1 の 4 条件と本ディレクトリ群の対応：

| 完了条件 | 主担当 | 補強 |
|---|---|---|
| (a) `alembic upgrade head` 冪等 | `postgres/01` | – |
| (b) 同一 CSV 2 回投入で行数増えず | `worker/05` | `worker/06` |
| (c) 月次サマリ SQL が手計算と一致 | `worker/07` | `worker/05`（投入元） |
| (d) 全ユニットテスト緑、`pyright` クリーン | 全タスク横断 | – |

## 6. 上位文書との関係

| 文書 | 関係 |
|---|---|
| `docs/plans/00-initial-design.md` | 設計書 v1.0（変更には ADR が必要） |
| `docs/plans/01-development-plan.md` | 全 Phase の本体プラン |
| `docs/plans/10-phase1-overview.md` | Phase1 全体俯瞰（タスク一覧・依存・実装順） |
| **`docs/plans/11-phase1-service-assignments.md`** | **本ファイル**：サービス別の振り分け |
| `docs/plans/02〜09-phase1-*.md` | Phase1 タスクごとの原典プラン（不変） |
| `docs/plans/{postgres,worker,api,ui}/` | サービス別実装タスクシート（本タスクで作成） |

## 7. Phase 2 以降の拡張方針

Phase 2 着手時に同様のサービス振り分けを行う。Phase 2 では：

- `worker` サービスに Phase 2.1〜2.8（Watcher / Gmail / メールパーサ / PayPal / cron）が集中
- `worker` に常駐サービス機能（watchdog）が加わるため、`docs/plans/worker/` に 2X 系の指示書が増える
- `docs/plans/postgres/` には新規スキーマ追加 ADR があれば対応指示書を増やす可能性がある
- `api` / `ui` は引き続き Phase 2 ではタスクなし（Phase 3 で本格着手）

サブディレクトリ構成は不変・追加方式で運用する。
