---
title: api サービス Phase3 タスク指示書
service: api
phase: 3
status: Ready
parent_index: docs/plans/13-phase3-service-assignments.md
last_updated: 2026-05-01
---

# api サービス Phase3 タスク指示書

`compose.yml` `api` サービス（Flask + Werkzeug 開発サーバ）は Phase 0 で `/health` のみのスタブが配備済み。Phase 3 で **REST API の本体実装**に着手する。

## サービス境界（Phase3 で本ディレクトリが扱うもの）

| 範囲 | パス |
|---|---|
| Flask アプリファクトリ拡張 | `src/kakeibo/api/app.py`（既存ファクトリに Blueprint / 認証 / OpenAPI を登録） |
| REST Blueprint 群 | `src/kakeibo/api/blueprints/{balances,transactions,categories,rules,aggregations}.py` |
| pydantic v2 リクエスト/レスポンスモデル | `src/kakeibo/api/schemas/` |
| 認証ミドルウェア（Tailscale ヘッダ） | `src/kakeibo/api/auth.py` |
| 共通エラーハンドラ | `src/kakeibo/api/errors.py` |
| OpenAPI 自動生成 | `src/kakeibo/api/openapi.py` |
| リポジトリ層（psycopg ベース、ORM 不採用） | `src/kakeibo/db/repositories/` |
| Categorizer（dry-run 用ロジック） | `src/kakeibo/categorizer/` |
| 集計 SQL（Phase 1.8 に追加） | `sql/queries/{monthly_balance_trend,category_spending,portfolio_composition}.sql` |
| API 関連テスト | `tests/unit/api/`, `tests/integration/api/`, `tests/unit/categorizer/` |

### このディレクトリでは扱わないもの

| 対象 | 帰属 |
|---|---|
| UI コンポーネント・ページ | `ui/Ph3/` |
| Playwright e2e | `ui/Ph3/06` |
| DB スキーマ追加 | なし（Phase 3 ではスキーマ変更しない） |
| Worker パイプライン変更 | なし（Phase 1〜2 で完了済） |

## タスク一覧

| 連番 | 担当タスク | 指示書 | 原典 | ブランチ | 優先度 |
|---|---|---|---|---|---|
| 01 | Phase 3.1 Flask REST API 主担当 | [`01-flask-rest-api.md`](./01-flask-rest-api.md) | §4.3 L309-319 | `feature/flask-rest-api` | 🔴 高 |
| 02 | Phase 3.3〜3.5 集計エンドポイント（補助） | [`02-aggregation-endpoints.md`](./02-aggregation-endpoints.md) | §4.3 L333-365 | `feature/api-aggregation-endpoints` | 🟡 中 |
| 03 | Phase 3.6 ルール dry-run（補助） | [`03-rule-dry-run-endpoint.md`](./03-rule-dry-run-endpoint.md) | §4.3 L367-377 | `feature/api-rule-dry-run` | 🟡 中 |

## 実行順序

```
[Phase 1 / Phase 2 完了] ←必須前提
   ↓
api/Ph3/01 (REST API 基盤)
   ├─→ api/Ph3/02 (集計)  ─┐
   └─→ api/Ph3/03 (dry-run)─┴─→ ui/Ph3/* と並行
```

`api/Ph3/02` と `api/Ph3/03` は `api/Ph3/01` 完了後に **2 並列**で着手可能（Coder 2体）。

## 共通の前提

- **Phase 1 / Phase 2 完了が必須**（特に Phase 1.6 取込CLI で DB に取引データが蓄積されていること）
- `flask-smorest` を runtime 依存に追加（`api/Ph3/01` で実施、その後の 02/03 は依存追加なし）
- 認証は `Tailscale-User-Login` ヘッダ前提、開発時は環境変数 `KAKEIBO_API_AUTH_BYPASS=1` でバイパス
- SQLAlchemy ORM は **不採用**（Phase 1 方針継続）。psycopg のパラメータ化クエリ + 薄いリポジトリ関数で永続化境界を保つ
- API レスポンスでは `transactions.raw_payload` を **返さない**（`docs/design/05-security-model.md` §10.2、PII 漏洩リスク）
- 日付返却は `Asia/Tokyo`（compose.yml `TZ` と整合）、内部処理は UTC

## 担当 Worker サブエージェント（モードB前提）

`agent-rules/91-claude-subagent-coding.md` に従う。

| Worker | 主な責務 |
|---|---|
| Planner | 認証ミドルウェアの責務分離、リポジトリ層の境界、エラー応答の DTO 設計 |
| Coder | テスト先行 → エンドポイント実装。`flask-smorest` ベースの自動 OpenAPI |
| Reviewer | SQL インジェクション耐性、認証バイパスの誤有効化リスク、`raw_payload` 漏洩、レート制限想定（家庭内なので最小） |
| Git-composer | アトミックコミット、`feature/*` ブランチ運用 |

並列ポリシー: `02` と `03` は `01` 完了後に同一メッセージで Coder 2体並列起動可。

## 共通の品質ゲート

```bash
pytest tests/unit/api/ tests/integration/api/ tests/unit/categorizer/
ruff check .
pyright
```

統合確認（`api/Ph3/01〜03` 全完了後）：
- `/api/openapi.json` から OpenAPI が取得でき、`openapi-typescript` で UI 側の型生成が成功
- `KAKEIBO_API_AUTH_BYPASS=1` での dev 起動から全 CRUD が叩ける
- 認証ヘッダなしで 401（本番想定）

## Phase3 完了条件カバレッジ（api 担当範囲）

| 完了条件 | 主担当タスク |
|---|---|
| (a) REST API CRUD 提供 | `01` + `02` + `03` |
| (c) UI からルール CRUD（API 側） | `01` + `03` |

(b) (d) (e) は ui 側の責務（`ui/Ph3/`）。
