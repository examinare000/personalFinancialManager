---
title: worker/Ph2/07 PayPal Transactions API クライアント
service: worker
phase_task_id: 2.7
priority: 高
source_plan: docs/plans/01-development-plan.md
source_section: §4.2 Phase 2.7（行 283-293）
branch: feature/adapter-paypal-api
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/Ph2/07 PayPal Transactions API クライアント（Phase 2.7）

## このファイルの位置付け

原典 §4.2 Phase 2.7 を `worker` 担当の指示書として展開。Phase 2.3〜2.6 とは **完全独立**（OAuth ではなく API Secret、メールではなく REST API）。Phase2 完了条件 (c)「PayPal Sandbox から取引取得」を直接満たす。

## 担当サービス

`worker` コンテナ。PayPal Transactions API v1（Sandbox / Live 両対応）を叩いて日次取引を取得し、`Transaction` に正規化する `PaypalApiAdapter`。レート制限（HTTP 429）に対する **指数バックオフ** を実装する。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `worker/Ph1/02`（IngestAdapter ABC） |
| 下流 | `worker/Ph2/08`（cron バッチ） |

`worker/Ph2/03〜06` と完全独立。

## 入力

1. **原典**: §4.2 Phase 2.7（行 283-293）
2. **アダプタ設計**: `worker/docs/design/02-ingest-adapters.md`
3. **セキュリティ**: `docs/design/05-security-model.md`
4. **ADR**: `docs/adr/007-adapter-pattern.md`, `docs/adr/011-no-credentials-storage.md`
5. **既存資産**:
   - `compose.yml` `worker` の secret `paypal_api_secret`、環境変数 `PAYPAL_API_SECRET_FILE=/run/secrets/paypal_api_secret`
   - `secrets/paypal_api_secret.txt.example`（フォーマット参考）
   - `shared/kakeibo_shared/config.py` の `paypal_api_secret: str | None` フィールド
6. **依存**: `httpx`（既宣言、`[project.dependencies]`）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `worker/src/kakeibo_worker/adapters/paypal.py` | `PaypalApiAdapter` 実装 |
| `worker/src/kakeibo_worker/adapters/_http.py` | 指数バックオフ付き HTTP クライアントヘルパ（PayPal 専用 or 汎用） |
| `tests/fixtures/paypal/sample_transaction_response.json` | PayPal API レスポンスの fixture |
| `tests/fixtures/paypal/rate_limit_response.json` | HTTP 429 レスポンス fixture |
| `tests/unit/adapters/test_paypal.py` | API モック + レート制限リトライ + 冪等性 |

## 実装方針

1. **クラス**: `PaypalApiAdapter(IngestAdapter)`、`source: ClassVar[str] = "paypal"`。
2. **認証フロー**:
   - `Settings.paypal_api_secret` から API Secret を読込
   - `client_id` は環境変数 `PAYPAL_CLIENT_ID`（compose.yml に追加 or `.env.example` に追記）
   - `POST /v1/oauth2/token` で **アクセストークン取得**（client_credentials grant）
   - アクセストークンの有効期限を保持し、期限切れで再取得
3. **取引取得**:
   - `GET /v1/reporting/transactions?start_date=...&end_date=...&fields=all`
   - 日付範囲は **取得時点の前日 0:00 UTC 〜 当日 0:00 UTC**（半開区間）の 1 日分を基本単位
4. **`Transaction` 正規化**:
   - `transaction_info.transaction_id` → description 末尾に含める（冪等性キー）
   - `transaction_info.transaction_amount.value` → `Decimal` で `amount`（`PaymentSent` 系は負、`PaymentReceived` 系は正に正規化）
   - `transaction_info.transaction_initiation_date` → `occurred_at`
   - 通貨コード → `currency`
5. **レート制限ハンドリング**: HTTP 429 で `Retry-After` ヘッダがあれば従う、なければ指数バックオフ（1 → 2 → 4 → 8 秒、最大 4 回）。失敗時は `AdapterError("PayPal rate limit exceeded")`。
6. **`extract_holdings`**: 空イテラブル。
7. **シークレット非露出**: `httpx` のリクエスト/レスポンスログ出力で `Authorization` ヘッダがマスクされること。`structlog` カスタムプロセッサで除去。

## 実装手順（TDD）

### 1. Red

- `tests/fixtures/paypal/sample_transaction_response.json` を Sandbox の実フォーマットに合わせて合成（実取引情報は禁止）。
- `tests/fixtures/paypal/rate_limit_response.json` で HTTP 429 + `Retry-After: 1` 形式。
- `tests/unit/adapters/test_paypal.py`：
  - 正常系: モック HTTP で 200 → `Transaction` リスト返却
  - レート制限: 1 回目 429 → 2 回目 200、ハンドリングが期待通り（スリープモック）
  - レート制限が 4 回連続で `AdapterError`
  - 冪等性: 同一 transaction_id で 2 回パースしてハッシュ一致
  - `Authorization` ヘッダがログに出ない

### 2. Green

- `worker/src/kakeibo_worker/adapters/_http.py` で `httpx.Client` をラップした `_request_with_backoff(method, url, **kwargs)` を実装。
- `worker/src/kakeibo_worker/adapters/paypal.py` で OAuth トークン取得 → 取引一覧取得 → `Transaction` 変換。
- 各テストを順に通す。

### 3. Refactor

- `_http.py` を **PayPal 専用にせず汎用化**（Phase 2.3 Gmail でも HTTP モックが必要なため）。Gmail との共通利用を検討。
- レート制限ハンドリングを `_RetryPolicy` dataclass にまとめてテスト容易化。

## 受入条件

- Sandbox 環境で日次取引が取得できる（実 Sandbox はオプション、テストは fixtures で代替）
- API Secret が `Settings.paypal_api_secret` 経由（Docker secret）でのみ読み込まれる
- レート制限時の指数バックオフが実装されている（最大 4 回 / `Retry-After` 優先）
- 取引 ID で冪等性が成立する（同一 transaction_id で行数増えず）
- `Authorization` ヘッダがログに出力されない（`caplog` で検証）
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
pytest tests/unit/adapters/test_paypal.py
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/adapter-paypal-api`
- コミット粒度（最低 5 件）：
  1. `テスト: PayPal API正常系/レート制限/冪等性/シークレット非露出のテストを先行作成`
  2. `機能: 指数バックオフ付きHTTPクライアントヘルパを追加`
  3. `機能: PayPal OAuth2トークン取得とアクセストークンキャッシュを実装`
  4. `機能: PaypalApiAdapter本体（取引取得・Transaction変換）を実装`
  5. `機能: 構造化ログでAuthorizationヘッダをマスクするプロセッサを追加`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 2.7 PayPal Transactions API クライアントを実装。

## 成果物
- worker/src/kakeibo_worker/adapters/paypal.py
- worker/src/kakeibo_worker/adapters/_http.py
- tests/fixtures/paypal/{sample_transaction_response,rate_limit_response}.json
- tests/unit/adapters/test_paypal.py

## 検証結果
- 全件緑（モック含む）
- レート制限ハンドリング動作確認
- caplog で Authorization 非露出を確認
- pyright / ruff: クリーン

## 既知の課題・申し送り
- 実 Sandbox 環境での試験は別途 secrets 整備後に運用検証として実施。

## 次のアクション提案
worker/Ph2/04, 05, 06, 07 が揃った時点で worker/Ph2/08 (cron) へ。
```

## 注意事項

- **API Secret をコードリテラルに書かない**。`Settings.paypal_api_secret` 経由で必ず読み込む。Git に絶対コミットしない。
- **Sandbox / Live の切替**: `PAYPAL_API_BASE` 環境変数で切替可能にする（Sandbox: `https://api-m.sandbox.paypal.com`、Live: `https://api-m.paypal.com`）。
- **クライアント ID の管理**: `client_id` は `secret` ではなく **公開可能な識別子** だが、`.env.example` に placeholder のみ書き、実値は環境ごとに設定する。
- **レート制限ポリシー**: `Retry-After` ヘッダがあれば優先、なければ指数バックオフ。最大リトライ数 4 を超えたら諦めて例外送出（過剰リトライによる課金 / アカウント制限を避ける）。
- **取引種別の符号**: PayPal API は `PaymentSent` / `PaymentReceived` 等で取引方向を示すが、`amount.value` の符号も同じ意味で出てくる。**`amount.value` の符号をそのまま採用**（独自に反転させない）。
- 日付境界は **UTC** で固定。タイムゾーン揺れを避ける。
