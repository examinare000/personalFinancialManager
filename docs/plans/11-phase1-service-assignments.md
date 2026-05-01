---
title: Phase1 サービス別タスク振り分けインデックス
phase: 1
status: Ready
parent: docs/plans/10-phase1-overview.md
last_updated: 2026-05-01
---

# Phase1 サービス別タスク振り分けインデックス

`docs/plans/10-phase1-overview.md`（Phase1 全体俯瞰）と `docs/plans/01-development-plan.md` §4.1（タスク詳細）を、`compose.yml` のサービス（コンテナ）単位に振り分けたディスパッチテーブル。

ADR-014 によりサービス専有のタスクプランは `<service>/docs/plans/PhN/` に同梱される。本ファイルはルート横断の振り分けインデックスとして機能する。

## 1. サービス × Phase1 タスク マトリクス

`compose.yml` のサービス名で振り分け。`postgres`（DB スキーマ・ドメイン型・SQL）と `worker`（取込パイプライン）に責務を集約し、`api` / `ui` は Phase1 では新規タスクなし。

| サービス | Phase 1.1 | 1.2 | 1.3 | 1.4 | 1.5 | 1.6 | 1.7 | 1.8 | 担当数 |
|---|---|---|---|---|---|---|---|---|---|
| `postgres` | ● | ● | – | – | – | – | – | ● | 3 |
| `worker` | – | – | ● | ● | ● | ● | ● | – | 5 |
| `api` | – | – | – | – | – | – | – | – | 0 |
| `ui` | – | – | – | – | – | – | – | – | 0 |

`postgres` は **スキーマ正本**（Alembic migrations）と **ドメイン型 / SQL クエリ** を所有するサービス。`worker` はそれを使うアプリケーション層（アダプタ・取込 CLI・冪等性検証）を担う。

## 2. サービス別ディレクトリ構成（ADR-014）

```
.
├── docs/plans/                              # 横断俯瞰のみ
│   ├── 00-initial-design.md
│   ├── 01-development-plan.md
│   ├── 10-phase1-overview.md                # Phase1 全体俯瞰
│   ├── 11-phase1-service-assignments.md     # 本ファイル
│   ├── 12-phase2-service-assignments.md
│   └── 13-phase3-service-assignments.md
│
├── postgres/docs/plans/Ph1/
│   ├── 02-db-schema-and-migrations.md       # Phase 1.1
│   ├── 03-domain-types.md                   # Phase 1.2
│   └── 09-monthly-summary-sql.md            # Phase 1.8
│
└── worker/docs/plans/Ph1/
    ├── 04-ingest-adapter-base.md            # Phase 1.3
    ├── 05-mufg-csv-adapter.md               # Phase 1.4
    ├── 06-smbc-csv-adapter.md               # Phase 1.5
    ├── 07-ingest-cli.md                     # Phase 1.6
    └── 08-hash-idempotency-tests.md         # Phase 1.7
```

各タスクプランファイルは **原典かつ唯一のタスク指示書**（ADR-014 で旧 `docs/plans/<service>/` の subagent 翻案シートは削除済み）。Coder / Planner サブエージェントは本ファイル経由で所属サービスの Ph1 配下に直接到達する。

## 3. 現在の実装状況スナップショット（2026-05-01 時点）

Phase 1.1〜1.8 の 8 タスクは **すべて未着手**。既に存在するのは Phase 0 のインフラ：

| 完了済（Phase 0） | パス |
|---|---|
| Docker Compose 構成 | `compose.yml`, `compose.override.yml`, `caddy/Caddyfile` |
| Postgres コンテナ | `compose.yml` `postgres` サービス（`postgres:16-alpine`） |
| Worker heartbeat ループ | `worker/src/kakeibo_worker/main.py`, `worker/Dockerfile` |
| API ヘルスチェック | `api/src/kakeibo_api/app.py` `/health`, `api/Dockerfile` |
| UI 雛形 | `ui/src/app/{layout,page}.tsx`, `ui/Dockerfile` |
| 設定ローダー | `shared/kakeibo_shared/config.py`, `shared/kakeibo_shared/logging.py` |
| Alembic 設定 | `postgres/src/alembic.ini`, `postgres/src/alembic/env.py`（versions は空） |
| DB セッション骨格 | `shared/kakeibo_shared/db/session.py` |
| Phase1 計画文書 | 本ファイル + 上記サービス別 Ph1/ ディレクトリ |
| 計画文書の構造検証テスト | `tests/unit/test_phase1_plan_documents.py` |

Phase1 のドメインロジック（`shared/kakeibo_shared/domain/`, `worker/src/kakeibo_worker/adapters/`, `worker/src/kakeibo_worker/ingest/`）は **すべて namespace package のプレースホルダ** のみで、実装は本タスクシート群でこれから着手する。

## 4. 推奨実装フロー（モードB: Claude単体サブエージェント協調）

`agent-rules/91-claude-subagent-coding.md` に従い、メインClaudeはオーケストレーターに徹する。実装フローは `docs/plans/10-phase1-overview.md` §3 を踏襲：

```
1. postgres/Ph1/02       （Planner → Coder → Reviewer → Git-composer）
2. postgres/Ph1/03       （同上）
3. worker/Ph1/04         （同上）
4. worker/Ph1/05 ‖ worker/Ph1/06   （Coder 2 体並列起動可能）
5. worker/Ph1/07         （同上）
6. worker/Ph1/08 ‖ postgres/Ph1/09 （並列可能）
```

各タスクは 1 ブランチ・1 PR 単位（`agent-rules/10-git-strategy.md`）。コミットはアトミックに分割し、コミットメッセージは日本語 1〜2 文（`機能:` / `修正:` / `テスト:` / `文書:` 等）。

## 5. Phase1 完了条件カバレッジ

`docs/plans/01-development-plan.md` §3.1 の 4 条件と本振り分けの対応：

| 完了条件 | 主担当 | 補強 |
|---|---|---|
| (a) `alembic upgrade head` 冪等 | `postgres/Ph1/02` | – |
| (b) 同一 CSV 2 回投入で行数増えず | `worker/Ph1/07` | `worker/Ph1/08` |
| (c) 月次サマリ SQL が手計算と一致 | `postgres/Ph1/09` | `worker/Ph1/07`（投入元） |
| (d) 全ユニットテスト緑、`pyright` クリーン | 全タスク横断 | – |

## 6. 上位文書との関係

| 文書 | 関係 |
|---|---|
| `docs/plans/00-initial-design.md` | 設計書 v1.0（変更には ADR が必要） |
| `docs/plans/01-development-plan.md` | 全 Phase の本体プラン |
| `docs/plans/10-phase1-overview.md` | Phase1 全体俯瞰（タスク一覧・依存・実装順） |
| **`docs/plans/11-phase1-service-assignments.md`** | **本ファイル**：サービス別の振り分け |
| `<service>/docs/plans/Ph1/*.md` | 各サービスの Phase1 タスク指示書（原典かつ唯一） |
| `docs/adr/013-service-colocated-design.md` / `docs/adr/014-per-service-source-layout.md` | サービス境界配置の意思決定 |

## 7. Phase 2 以降の拡張方針

Phase 2 着手時に同様のサービス振り分けを行う。Phase 2 では：

- `worker` サービスに Phase 2.1〜2.8（Watcher / Gmail / メールパーサ / PayPal / cron）が集中（`worker/docs/plans/Ph2/`）
- `worker` に常駐サービス機能（watchdog）が加わるため、Phase 2 サービス振り分けは `docs/plans/12-phase2-service-assignments.md` を参照
- `postgres/docs/plans/` には新規スキーマ追加 ADR があれば対応指示書を増やす可能性がある
