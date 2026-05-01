---
title: api/Ph3/01 Flask REST API
service: api
phase_task_id: 3.1
priority: 高
source_plan: docs/plans/01-development-plan.md
source_section: §4.3 Phase 3.1（行 309-319）
branch: feature/flask-rest-api
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# api/Ph3/01 Flask REST API（Phase 3.1）

## このファイルの位置付け

原典 `docs/plans/01-development-plan.md` §4.3 Phase 3.1 を `api` サービス担当の指示書として展開。Phase3 完了条件 (a)「Flask REST API が CRUD を提供する」を直接満たす。Phase 3 の **クリティカルパス起点**。原典との乖離時は原典優先。

## 担当サービス

`compose.yml` `api` サービス（Flask + Werkzeug、`api/Dockerfile` の uv マルチステージ）。Phase 0 の `/health` のみのスタブを **本格的な REST API** に拡張する。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `worker/Ph1/05`（取込CLI 完了 → DB に取引データがある） + `postgres/Ph1/01`（スキーマ確定） |
| 下流 | `api/Ph3/02`（集計）, `api/Ph3/03`（dry-run）, `ui/Ph3/01`〜`05` |

Phase 2 完了は望ましいが必須ではない（Phase 1.6 で投入された CSV だけでもテストデータとしては成立）。

## 入力（Coder が読むべきファイル）

1. **原典**: `docs/plans/01-development-plan.md` §4.3 Phase 3.1（行 309-319）
2. **デプロイ**: `docs/design/04-deployment-stack.md` §3 / §6（Caddy + api 経路）
3. **セキュリティ**: `docs/design/05-security-model.md` §11（Tailscale 認証）, §10.2（`raw_payload` の扱い）
4. **ADR**: `docs/adr/009-nas-docker-compose.md`, `docs/adr/010-tailscale-only-access.md`
5. **既存 API**: `api/src/kakeibo_api/{app.py, __main__.py, __init__.py}`, `api/Dockerfile`
6. **設定ローダー**: `shared/kakeibo_shared/config.py`（`KAKEIBO_API_AUTH_BYPASS` フィールド追加先）
7. **ドメイン型**: `shared/kakeibo_shared/domain/`（Phase 1.2 で実装される `Transaction` / `Holding` / `BalanceSnapshot`）
8. **既存テスト**: `tests/unit/test_settings_repr.py`（破壊しないこと）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `pyproject.toml` | `flask-smorest>=0.44,<1`, `marshmallow>=3.21,<4` を `[project.dependencies]` に追加 |
| `shared/kakeibo_shared/config.py` | `auth_bypass: bool = False`（`KAKEIBO_API_AUTH_BYPASS` で上書き）追加 |
| `api/src/kakeibo_api/app.py` | ファクトリで Blueprint / 認証 / エラー / OpenAPI を登録 |
| `api/src/kakeibo_api/auth.py` | `Tailscale-User-Login` ヘッダ検証 + dev バイパス |
| `api/src/kakeibo_api/errors.py` | 共通エラーハンドラ（4xx / 5xx の JSON 化） |
| `api/src/kakeibo_api/openapi.py` | flask-smorest の `Api` インスタンス生成 + `/api/openapi.json` + Swagger UI |
| `api/src/kakeibo_api/blueprints/__init__.py` | Blueprint 集約 |
| `api/src/kakeibo_api/blueprints/balances.py` | `GET /api/balances`（口座別最新残高） |
| `api/src/kakeibo_api/blueprints/transactions.py` | `GET /api/transactions`（ページネーション + フィルタ） |
| `api/src/kakeibo_api/blueprints/categories.py` | `GET/POST/PUT/DELETE /api/categories` |
| `api/src/kakeibo_api/blueprints/rules.py` | `GET/POST/PUT/DELETE /api/rules`（dry-run は `api/Ph3/03` で追加） |
| `api/src/kakeibo_api/schemas/__init__.py` | スキーマ集約 |
| `api/src/kakeibo_api/schemas/{balance,transaction,category,rule,common}.py` | pydantic v2 モデル |
| `shared/kakeibo_shared/db/repositories/__init__.py` | リポジトリ基底 |
| `shared/kakeibo_shared/db/repositories/{balances,transactions,categories,rules}.py` | psycopg ベースの薄いラッパ |
| `tests/unit/api/__init__.py` | 新規 |
| `tests/unit/api/conftest.py` | Flask test client + 認証バイパス fixture |
| `tests/unit/api/test_{balances,transactions,categories,rules,auth,openapi}.py` | エンドポイント契約テスト |
| `tests/integration/api/__init__.py` | 新規 |
| `tests/integration/api/test_crud_e2e.py` | testcontainers Postgres + フィクスチャ投入で CRUD 統合確認 |

## 実装方針

### 1. OpenAPI 生成: `flask-smorest` 採用

- `flask-smorest` は pydantic v2 と直接連携し、`@blp.arguments` / `@blp.response` デコレータで自動的にスキーマ・ドキュメントが生成される
- `apispec` 単体や `flask-pydantic-spec` は手書き spec が増える / 活発さが低いため不採用
- `marshmallow` は flask-smorest が依存として要求するため `[project.dependencies]` に明示

### 2. 認証: Caddy + `Tailscale-User-Login` ヘッダ前提

- 本番では Caddy が `tsidp` でユーザを認証し `Tailscale-User-Login` ヘッダを後段の Flask に伝播（`docs/design/05-security-model.md` §11）
- API ミドルウェアは **ヘッダの存在確認のみ**（実際の認可は Tailscale が担当）
- 開発環境では `Settings.auth_bypass=True`（環境変数 `KAKEIBO_API_AUTH_BYPASS=1`）でミドルウェアをスキップ
- **本番ビルドで誤って bypass が有効化されない** ことを `tests/unit/api/test_auth.py` で検証（既定値 `False`、Settings.__repr__ でマスクなしで露出）

### 3. 永続化層: psycopg + 薄いリポジトリ関数

- SQLAlchemy ORM は **不採用**（Phase 1 方針継承）
- 各リポジトリ関数は `def list_transactions(conn: psycopg.Connection, *, from_date: date, ...) -> list[TransactionDTO]` の形式
- パラメータ化クエリ（`%s` プレースホルダ）で SQL インジェクション対策
- 接続管理は Flask の `g` オブジェクト + `@app.teardown_appcontext` で行う（リクエスト単位の接続/解放）

### 4. エラー応答 DTO

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request",
    "details": {"field": "name", "reason": "required"}
  }
}
```

### 5. CORS 不採用

- Caddy が `/` → ui:3000、`/api/*` → api:8000 を **同一オリジン**で配信するため CORS は不要（YAGNI）
- 本番想定では Tailscale 配下の単一ホスト名で UI と API がアクセスされる

### 6. レスポンスから `raw_payload` を除外

- `transactions.raw_payload` JSONB は EC 注文番号や PayPal メタデータを含むため、API レスポンスでは **省略**
- `TransactionResponse` スキーマで明示的に未含

### 7. ページネーション規約

- `?page=1&limit=50`（既定 `limit=100`、上限 `limit=1000`）
- レスポンスメタ: `{data: [...], meta: {total: N, page: 1, limit: 50, has_next: bool}}`

### 8. 日付・通貨

- 日付返却は `YYYY-MM-DD`（タイムゾーンなし、Asia/Tokyo 想定）
- 金額は `Decimal` を `string` でシリアライズ（`float` 経由による精度損失防止）
- 通貨コードは ISO 4217 3 文字大文字

## 実装手順（TDD: Red → Green → Refactor）

### 0. ブランチ作成

```bash
git checkout develop && git pull origin develop
git checkout -b feature/flask-rest-api
```

### 1. Red: テストを先に書く

`tests/unit/api/conftest.py` で Flask test client + auth bypass fixture を用意。各エンドポイントに以下を記述：

- `test_get_transactions_returns_paginated_list()`：50 件以下、`{data, meta: {total,page,limit}}` 構造
- `test_get_transactions_filters_by_date_range()`：`?from=&to=` でフィルタ
- `test_get_transactions_excludes_raw_payload()`：レスポンスに `raw_payload` キー無し
- `test_post_categories_validates_required_fields()`：`name` 欠落で 422
- `test_put_rule_priority_persists_change()`
- `test_delete_rule_removes_persisted_row()`
- `test_unauthorized_when_tailscale_header_missing()`：401 + エラー DTO
- `test_dev_bypass_allows_anonymous_access()`：`KAKEIBO_API_AUTH_BYPASS=1` で 200
- `test_settings_auth_bypass_default_is_false()`：本番安全性確認
- `test_openapi_endpoint_returns_valid_spec()`：`paths` / `components.schemas` を含む

`tests/integration/api/test_crud_e2e.py` で testcontainers + `worker/Ph1/05` の取込CLIフィクスチャを使い、`POST /api/categories` → `GET` で永続化確認。

`pytest tests/unit/api/ tests/integration/api/` で全件赤を確認。

### 2. Green: 最小実装で順に通す

1. `pyproject.toml` に `flask-smorest`, `marshmallow` 追加 → `uv sync`
2. `shared/kakeibo_shared/config.py` に `auth_bypass` 追加（既存テストを破壊しないよう既定値 `False`、`__repr__` のマスク非対象）
3. `api/src/kakeibo_api/openapi.py` で `flask_smorest.Api` インスタンス生成
4. `api/src/kakeibo_api/auth.py` で `before_request` ハンドラを実装（bypass フラグ読み取り）
5. `api/src/kakeibo_api/errors.py` で `errorhandler(HTTPException)` を実装
6. `api/src/kakeibo_api/schemas/*.py` を pydantic v2 で実装
7. `shared/kakeibo_shared/db/repositories/*.py` を実装
8. `api/src/kakeibo_api/blueprints/*.py` を実装（balances → transactions → categories → rules の順）
9. `api/src/kakeibo_api/app.py` のファクトリで全部を登録

### 3. Refactor

- 重複するエラー DTO 生成を `errors.make_error_response(code, message, details=None, status=400)` に集約
- リポジトリ共通の接続取得を `_get_conn()` に抽出
- pydantic スキーマの `Config` 共通化

## 受入条件

原典 §4.3 Phase 3.1 の受入基準に加えて：

- `GET /api/balances`, `GET /api/transactions`, `GET/POST/PUT/DELETE /api/categories`, `GET/POST/PUT/DELETE /api/rules` がすべて動作
- OpenAPI スキーマが `/api/openapi.json` から取得でき、Swagger UI が `/api/docs`（または `/api/swagger`）で表示される
- 認証は Tailscale ヘッダ前提で localhost / Tailnet からのみ受理
- `pytest` + Flask test client で全エンドポイント緑
- `KAKEIBO_API_AUTH_BYPASS` の既定値が `False`（本番安全性）
- レスポンスに `transactions.raw_payload` が含まれない
- ページネーション既定 `limit=100`、上限 `limit=1000` を超えるリクエストで 422
- `pyright` クリーン、`ruff` 違反ゼロ
- 既存テスト（`tests/unit/test_settings_repr.py` 等）が緑のまま

## 品質ゲート

```bash
pytest tests/unit/api/ tests/integration/api/
pytest tests/unit/test_settings_repr.py  # 既存破壊チェック
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/flask-rest-api`
- コミット粒度（最低 7 件、`agent-rules/10-git-strategy.md` 準拠）：
  1. `テスト: REST APIのCRUD・認証・OpenAPIエンドポイントのテストを先行作成`
  2. `設定: flask-smorestとmarshmallowをruntime依存に追加`
  3. `機能: Settings.auth_bypassフィールドを追加（本番既定False）`
  4. `機能: APIスキーマ（pydantic v2モデル）と共通エラーハンドラを実装`
  5. `機能: Tailscaleヘッダ前提の認証ミドルウェアを実装（devバイパス付き）`
  6. `機能: psycopgベースのリポジトリ層（balances/transactions/categories/rules）を実装`
  7. `機能: balances/transactions/categories/rulesのBlueprintを実装`
  8. `機能: OpenAPIスキーマ生成とSwagger UI公開を有効化`
  9. `機能: app factoryに全Blueprint・認証・エラーハンドラ・OpenAPIを登録`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 3.1 Flask REST API を実装。

## 成果物
- pyproject.toml（flask-smorest, marshmallow 追加）
- api/src/kakeibo_api/{app.py, auth.py, errors.py, openapi.py}
- api/src/kakeibo_api/blueprints/{balances,transactions,categories,rules}.py
- api/src/kakeibo_api/schemas/{balance,transaction,category,rule,common}.py
- shared/kakeibo_shared/db/repositories/{balances,transactions,categories,rules}.py
- shared/kakeibo_shared/config.py（auth_bypass 追加）
- tests/unit/api/* / tests/integration/api/*

## 検証結果
- pytest（unit + integration）: 全件緑
- /api/openapi.json valid
- 認証バイパス既定 False / Tailscale ヘッダ無しで 401
- pyright / ruff: クリーン
- 既存テスト破壊なし

## 次のアクション提案
api/Ph3/02 (集計) と api/Ph3/03 (dry-run) を 2 並列で着手可能。
ui/Ph3/01 (React雛形) も並行着手可能。
```

## 注意事項

- **既存テストを破壊しない**（`agent-rules/00-core-principles.md` §1）。`tests/unit/test_settings_repr.py` で `auth_bypass` フィールド追加時の挙動を要確認。
- **`auth_bypass` の本番誤有効化**を防ぐ：`Settings` のデフォルト値を `False`、テストで既定値を明示検証。`__repr__` ではマスクしない（運用診断のため可視化）。
- **`raw_payload` を絶対に返さない**：TransactionResponse スキーマで明示除外し、テストで non-existence を検証。
- **Tailscale 認証実機テストは Phase 4.6** で実施。Phase 3 では unit test レベルでミドルウェア挙動のみ検証。
- **CORS は実装しない**（YAGNI、同一オリジン）。
- 集計エンドポイント（`/api/balances/monthly` 等）は本タスクでは扱わず `api/Ph3/02` で実装。
- ルール dry-run（`POST /api/rules/dry-run`）は本タスクでは扱わず `api/Ph3/03` で実装。
- SQLAlchemy ORM は **使わない**（Phase 1 方針継続）。psycopg のパラメータ化クエリで安全性担保。
