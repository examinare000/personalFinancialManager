---
title: api サービス Phase1 タスク指示書
service: api
phase: 1
status: NoTasks
parent_index: docs/plans/10-phase1-overview.md
last_updated: 2026-05-01
---

# api サービス Phase1 タスク指示書

## 結論：Phase1 では本サービス向けの新規実装タスクなし

`compose.yml` `api` サービス（Flask + Werkzeug 開発サーバ）は **Phase 0 で完了済み**。`/health` エンドポイントだけを提供する最小スタブで、`docker compose up -d` 後の HEALTHCHECK・Caddy 経由の疎通確認を満たす。

Phase 1 のタスク（1.1〜1.8）はすべて `postgres` または `worker` サービスに帰属する。`docs/plans/10-phase1-overview.md` §2 のタスク一覧と `docs/plans/01-development-plan.md` §4.1 を確認しても、API レイヤを変更する必要があるタスクは存在しない。

## サービス境界（参考）

| 範囲 | パス |
|---|---|
| Flask アプリケーションファクトリ | `src/kakeibo/api/app.py`（`/health` のみ） |
| エントリポイント | `src/kakeibo/api/__main__.py` |
| Phase3 で REST 拡張する Blueprint | （未配置）`src/kakeibo/api/blueprints/` 想定 |
| api コンテナ Dockerfile | `api/Dockerfile`（uv マルチステージ） |
| api コンテナ wrapper | `api/kakeibo_api/__init__.py`（`create_app` 再エクスポートのみ） |

`api` コンテナの Dockerfile は `src/kakeibo` 全体を COPY するため、`worker/01〜07` で実装した共通ライブラリ（domain / adapters / ingest / sql）も同じ image に含まれる。Phase 3.1 で REST API を実装する際はこれを再利用する。

## Phase1 の間に api サービスへ波及する変更（許容例）

ロジックは増やさないが、以下のような **間接的な影響** はあり得る：

| 変更例 | 受入可否 | 備考 |
|---|---|---|
| `pyproject.toml` の `[project.dependencies]` 追加 | 可（再ビルド必要） | `worker` 側のタスクで `click` 等を使う場合、共通の依存定義を更新するため `api` イメージも再ビルドされる |
| `src/kakeibo/__init__.py` の `__version__` 変更 | 可 | リリース時に同じコミットで `pyproject.toml` の `version` と同期 |
| `src/kakeibo/config.py`, `logging.py` の改修 | 慎重に | 既存テスト（`tests/unit/test_settings_repr.py` など）を壊さないこと |
| `api/Dockerfile` の変更 | 原則不要 | Phase 1 内では変更不要のはず。必要になったら別タスク化 |

これらは **既存の動作を壊さない** ことを最優先する（`agent-rules/00-core-principles.md` 絶対遵守の3原則 §1 デグレッション防止）。

## Phase 3.1 への申し送り

Phase 3 で本サービスに本格着手するときの起点：

- 原典: `docs/plans/01-development-plan.md` §4.3 Phase 3.1 Flask REST API
- ブランチ: `feature/flask-rest-api`
- 関連 ADR: ADR-009（NAS + Docker Compose）, ADR-010（Tailscale 限定アクセス）
- 関連 design: `docs/design/04-deployment-stack.md`, `docs/design/05-security-model.md`
- 想定エンドポイント: `GET /api/balances`, `GET /api/transactions`, `GET/POST/PUT/DELETE /api/categories`, `GET/POST/PUT/DELETE /api/rules`

Phase 3.1 着手時に本ディレクトリへ `01-flask-rest-api.md` 等の指示書を追加する。

## 担当 Worker サブエージェント

Phase1 期間中に発生する可能性があるのは **Reviewer のみ**：

| Worker | 役割 |
|---|---|
| Reviewer | `worker` 側のタスクが `pyproject.toml` や `src/kakeibo/__init__.py` を変更した際、`api` コンテナのビルド・起動に影響しないかを Read のみで確認 |

Coder / Planner / Git-composer の起動は Phase1 では原則不要。
