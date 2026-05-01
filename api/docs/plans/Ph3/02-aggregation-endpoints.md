---
title: api/Ph3/02 集計エンドポイント（残高推移・カテゴリ別支出・ポートフォリオ）
service: api
phase_task_id: 3.3-aux,3.4-aux,3.5-aux
priority: 中
source_plan: docs/plans/01-development-plan.md
source_section: §4.3 Phase 3.3〜3.5（行 333-365）
branch: feature/api-aggregation-endpoints
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# api/Ph3/02 集計エンドポイント（Phase 3.3〜3.5 補助）

## このファイルの位置付け

原典 §4.3 Phase 3.3 / 3.4 / 3.5 の **API 側補助タスク**。原典 3.1 の受入基準は CRUD 止まりで集計 API は明示されていないため、3.3〜3.5（UI 側のグラフ系）が必要とする集計エンドポイントを Planner 判断で本タスクに分離した。

## 担当サービス

`compose.yml` `api` サービス。`api/Ph3/01` で構築した Blueprint 基盤に **集計専用の Blueprint** を追加し、Phase 1.8 の月次サマリ SQL を再利用 + 拡張する。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `api/Ph3/01`（REST API 基盤）+ `worker/Ph1/07`（月次サマリ SQL）+ Phase 1〜2 の `holdings` / `balance_snapshots` 投入 |
| 下流 | `ui/Ph3/02`（月次推移）, `ui/Ph3/03`（カテゴリ別）, `ui/Ph3/04`（ポートフォリオ） |

`api/Ph3/03` と並列着手可能。

## 入力

1. **原典**: `docs/plans/01-development-plan.md` §4.3 Phase 3.3 / 3.4 / 3.5（行 333-365）
2. **データモデル**: `postgres/docs/design/01-data-model.md`（`balance_snapshots`, `holdings`, `transactions`, `categories`）
3. **分類エンジン**: `worker/docs/design/03-categorization-engine.md` §6（`category_source` フィルタ）
4. **既存資産**: `postgres/src/sql/queries/monthly_summary.sql`（Phase 1.8 で実装される月次サマリ）
5. **API 基盤**: `api/Ph3/01-flask-rest-api.md` で実装される `flask-smorest` 連携、リポジトリ層パターン

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `postgres/src/sql/queries/monthly_balance_trend.sql` | 全口座合計残高の月次推移 |
| `postgres/src/sql/queries/category_spending.sql` | 月別カテゴリ別支出（親→子ドリルダウン対応） |
| `postgres/src/sql/queries/portfolio_composition.sql` | `holdings.symbol_kind` 別構成比 + 直近スナップショット日付 |
| `api/src/kakeibo_api/schemas/aggregations.py` | レスポンスモデル（`MonthlyBalance`, `CategorySpending`, `PortfolioComposition`） |
| `api/src/kakeibo_api/blueprints/aggregations.py` | `GET /api/balances/monthly`, `GET /api/categories/spending`, `GET /api/holdings/composition` |
| `shared/kakeibo_shared/db/repositories/aggregations.py` | 上記 SQL を psycopg で呼ぶ薄いラッパ |
| `api/src/kakeibo_api/app.py` | aggregations Blueprint を登録（既存ファクトリへ追記） |
| `tests/integration/api/test_aggregations.py` | testcontainers + 決定的フィクスチャで集計値の正当性検証 |
| `tests/unit/api/test_aggregations_validation.py` | クエリパラメータバリデーション |

## 実装方針

### 1. 集計は SQL 側で行う

- API 層で Python 集計しない。理由：取引数が増えても性能を保つ + Phase 1.8 と整合。
- 各 SQL は `:from`, `:to` パラメータで期間指定（半開区間 `[from, to)`）。

### 2. 月次残高推移 (`/api/balances/monthly`)

```sql
-- monthly_balance_trend.sql（概略）
WITH monthly_snapshots AS (
    SELECT
        date_trunc('month', as_of_date)::date AS month,
        account_id,
        balance,
        ROW_NUMBER() OVER (PARTITION BY account_id, date_trunc('month', as_of_date) ORDER BY as_of_date DESC) AS rn
    FROM balance_snapshots
    WHERE as_of_date >= :date_from AND as_of_date < :date_to
)
SELECT
    month,
    SUM(balance) AS total_balance
FROM monthly_snapshots
WHERE rn = 1
GROUP BY month
ORDER BY month;
```

- 既定: 直近 12 か月（`from = today - 12 months`、`to = today + 1 day`）
- レスポンス: `{data: [{month: "2026-04", total_balance: "1234567.00"}, ...]}`

### 3. カテゴリ別支出 (`/api/categories/spending`)

- 親カテゴリで集計 + `?parent_id=X` で子カテゴリへドリルダウン
- 未分類取引（`category_id IS NULL`）は `null_category` キーで明示返却（**「未分類」のローカライズは UI 側の責務**）
- レスポンス例:
  ```json
  {
    "month": "2026-04",
    "categories": [
      {"id": 1, "name": "食費", "amount": "23000.00", "parent_id": null, "has_children": true},
      {"id": null, "name": null, "amount": "5000.00", "parent_id": null, "has_children": false}
    ]
  }
  ```

### 4. ポートフォリオ構成 (`/api/holdings/composition`)

- `symbol_kind` 別の評価額合計と構成比を計算
- 評価額 NULL の銘柄は別配列 `warnings` に列挙（原典 §4.3 Phase 3.5 受入基準と整合）
- `snapshot_date`（直近スナップショット日付）を併せて返却
- レスポンス例:
  ```json
  {
    "snapshot_date": "2026-04-30",
    "composition": [
      {"symbol_kind": "stock_jp", "total_value": "500000.00", "ratio": 0.4},
      {"symbol_kind": "fund", "total_value": "750000.00", "ratio": 0.6}
    ],
    "warnings": [
      {"symbol": "XXXX", "symbol_kind": "stock_us", "last_seen": "2026-03-15"}
    ]
  }
  ```

### 5. クエリパラメータバリデーション

- 全エンドポイントで `?from=YYYY-MM-DD&to=YYYY-MM-DD` を受理（月単位の場合は `from=YYYY-MM-01`）
- 未指定時は既定値（直近 12 か月 / 当月）
- 不正な日付フォーマット → 422

### 6. 認証

- `api/Ph3/01` の認証ミドルウェアを継承（個別実装不要）

### 7. 空データ時

- `200 + {data: []}` または `{categories: []}` を返す（404 は採用しない、UI の空状態表示と整合）

## 実装手順（TDD）

### 1. Red

- `tests/unit/api/test_aggregations_validation.py` でクエリパラメータバリデーション
- `tests/integration/api/test_aggregations.py` で testcontainers + フィクスチャ：
  - `test_monthly_balance_trend_returns_12_months_by_default()`
  - `test_monthly_balance_trend_with_custom_range()`
  - `test_category_spending_drilldown_includes_subcategories()`
  - `test_category_spending_marks_uncategorized()`（`null_category` キーで返却）
  - `test_portfolio_composition_separates_null_value_holdings()`
  - `test_aggregations_return_empty_data_when_no_records()`
  - `test_aggregations_require_auth()`

### 2. Green

1. `postgres/src/sql/queries/monthly_balance_trend.sql` を実装
2. `postgres/src/sql/queries/category_spending.sql` を実装
3. `postgres/src/sql/queries/portfolio_composition.sql` を実装
4. `shared/kakeibo_shared/db/repositories/aggregations.py` を実装
5. `api/src/kakeibo_api/schemas/aggregations.py` を実装
6. `api/src/kakeibo_api/blueprints/aggregations.py` を実装
7. `app.py` ファクトリに Blueprint 登録

### 3. Refactor

- 期間パラメータの解釈ロジックを `_parse_date_range(from_str, to_str, default_months=12)` に抽出
- SQL ファイル読込ヘルパは Phase 1.8 の `src/kakeibo/sql/runner.py` を再利用

## 受入条件

- 同一データセットを SQL 直接実行と API 経由で取得した値が完全一致
- 空データ時に `200 + {data: []}` を返す（404 ではない）
- レスポンス時間が pytest 計測で 1 リクエストあたり 200ms 以内（家庭内データ規模前提）
- 全エンドポイントで認証必須（`api/Ph3/01` のミドルウェア継承）
- OpenAPI スキーマに集計エンドポイントが反映される
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
pytest tests/integration/api/test_aggregations.py tests/unit/api/test_aggregations_validation.py
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/api-aggregation-endpoints`
- コミット粒度（最低 5 件）：
  1. `テスト: 集計エンドポイント（残高推移・カテゴリ別支出・ポートフォリオ）のテストを先行作成`
  2. `機能: 月次残高推移SQLとリポジトリを追加`
  3. `機能: カテゴリ別支出SQLとドリルダウン対応リポジトリを追加`
  4. `機能: ポートフォリオ構成SQLとNULL評価額警告ロジックを追加`
  5. `機能: aggregations BlueprintをOpenAPIに登録`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 3.3〜3.5 集計エンドポイントを実装。

## 成果物
- sql/queries/{monthly_balance_trend,category_spending,portfolio_composition}.sql
- api/src/kakeibo_api/blueprints/aggregations.py
- api/src/kakeibo_api/schemas/aggregations.py
- shared/kakeibo_shared/db/repositories/aggregations.py
- tests/integration/api/test_aggregations.py
- tests/unit/api/test_aggregations_validation.py

## 検証結果
- pytest 全件緑
- レスポンス時間 < 200ms
- pyright / ruff: クリーン

## 次のアクション提案
ui/Ph3/02 / 03 / 04 が 3 並列で着手可能。
```

## 注意事項

- **未分類カテゴリ**: API は `null_category` キーで返し、表示文言（「未分類」「その他」など）は UI 側で決定。
- **金額は文字列**で返却（`Decimal` 精度保持）。UI 側で `Intl.NumberFormat` で整形。
- **タイムゾーン**: 期間境界はローカル日付（Asia/Tokyo）として扱う。SQL 内の `date_trunc` も Asia/Tokyo 想定。
- **`category_source` フィルタ**: 集計対象は全 `category_source`（`rule`, `llm`, `manual`, `NULL`）を含む。Phase 4 で「LLM 分類のみ除外」のような切替を入れる場合は別パラメータで追加。
- **ポートフォリオ snapshot_date**: 全口座の最新 snapshot_date を集約してレスポンス。各口座でズレがある場合は最も古いものを返す（保守的）。
- **インデックス追加は本タスクでは行わない**（実データで遅延が顕在化したら別タスクで追加、原典 §スコープ「含まない」と整合）。
