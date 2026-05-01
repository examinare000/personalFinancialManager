---
title: api サービス Phase2 タスク指示書
service: api
phase: 2
status: NoTasks
parent_index: docs/plans/12-phase2-service-assignments.md
last_updated: 2026-05-01
---

# api サービス Phase2 タスク指示書

## 結論：Phase2 では本サービス向けの新規実装タスクなし

`compose.yml` `api` サービス（Flask + Werkzeug 開発サーバ）は Phase 0 で完了済み（`/health` のみ）。Phase 1 と同様、Phase 2 でも **新規エンドポイントを追加しない**。

`docs/plans/01-development-plan.md` §4.2 のタスク 2.1〜2.8 はすべて `worker` サービス内部で完結する自動取込パイプラインで、外部から HTTP で叩く対象ではない。

## サービス境界（参考）

| 範囲 | Phase 2 での扱い |
|---|---|
| `/health` エンドポイント | 既存のまま維持（HEALTHCHECK / Caddy 疎通用） |
| Phase 3 で追加予定の REST エンドポイント | 着手しない（Phase 3.1 で `feature/flask-rest-api`） |

## Phase2 の間に api サービスへ波及する変更（許容例）

| 変更例 | 受入可否 | 備考 |
|---|---|---|
| `pyproject.toml` への runtime 依存追加（`watchdog`, `apscheduler`, `google-auth` 等） | 可（再ビルド必要） | `worker/Ph2/01,03,08` で発生。`api` イメージにも反映されるが API 機能は変わらない |
| `src/kakeibo/__init__.py` の `__version__` 更新 | 可 | リリース時の同期 |
| `src/kakeibo/config.py` 改修 | 慎重に | `Settings` 既存フィールド（`paypal_api_secret`, `gmail_oauth_token_path`）を **API 側が import しても壊れない** ことが必要 |
| `api/Dockerfile` 変更 | 不要 | – |

`agent-rules/00-core-principles.md` の3原則 §1 デグレッション防止と整合：既存の `/health` レスポンスや `pytest tests/unit/` を壊さないこと。

## Phase 3.1 への申し送り

Phase 3 で本サービスに本格着手するときの起点：

- 原典: `docs/plans/01-development-plan.md` §4.3 Phase 3.1 Flask REST API
- ブランチ: `feature/flask-rest-api`
- Phase 2 で作成された `RawMail`, メールパーサ群, PayPal Adapter, Watcher が `src/kakeibo/` 配下に揃う想定なので、API は **既存ロジックを呼び出すだけ** の薄いレイヤとして実装可能になる
- 想定エンドポイント: `GET /api/transactions`（Phase 2 で投入された取引も返却対象）

Phase 3.1 着手時に `docs/plans/api/Ph3/01-flask-rest-api.md` を新設する。

## 担当 Worker サブエージェント

Phase2 期間中の起動は **Reviewer のみ**：

| Worker | 役割 |
|---|---|
| Reviewer | `worker/Ph2/*` のタスクで `pyproject.toml` / `src/kakeibo/__init__.py` / `src/kakeibo/config.py` が変更された際、`api` コンテナのビルド・起動と既存テスト（`tests/unit/test_settings_repr.py` など）への影響をチェック |

Coder / Planner / Git-composer の起動は Phase2 では原則不要。
