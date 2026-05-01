---
title: Phase 1.8 月次サマリ SQL
phase: 1
task_id: 1.8
status: Draft
priority: 中
parent: docs/plans/01-development-plan.md
last_updated: 2026-04-30
---

# Phase 1.8 月次サマリ SQL

## タスク概要

Phase1 完了条件 (c)「SQL で月次サマリが手計算と一致」を満たす集計クエリを `postgres/src/sql/queries/monthly_summary.sql` として配置する。サンプルデータを投入してテストから呼び出し、Excel 等での手計算結果と完全一致することを保証する。

参照: `docs/plans/01-development-plan.md` §4.1 Phase 1.8, §3.1 完了条件 (c), `postgres/docs/design/01-data-model.md`。

## 目的・背景

### 目的

- 月別・カテゴリ別に集計した支出 / 収入額を返す SQL を `postgres/src/sql/queries/monthly_summary.sql` に配置する。
- カテゴリ未分類の取引も「その他」として集計から漏れないようにする。
- pytest からクエリを実行して、固定フィクスチャと期待 DataFrame を比較できる仕組みを作る。

### 背景

- Phase1 完了条件 (c) を直接満たすタスクであり、Phase1 全体の「動作する MVP」を最後に検証する位置付け。
- Phase 3.3 の月次推移グラフ、Phase 4.5 の Obsidian 月次サマリ出力でも本クエリ（または派生）を再利用するため、SQL ファイルとして独立配置することで再利用性を担保する。
- アプリ層から呼び出すか、`psql -f` で実行するかの選択肢があるが、Phase 3 で REST API から呼び出す前提で、Python 側にラッパー関数を用意する。

## スコープ

### 含む

- `postgres/src/sql/queries/monthly_summary.sql`（純 SQL ファイル、引数 `:year_month` などを `psycopg` 経由で展開）。
- 月別 × カテゴリ別の合計金額、取引件数、収入 / 支出別の小計。
- カテゴリ未分類取引の `その他` 列（または `category_id IS NULL` のグループ）への集計。
- pytest からクエリを実行するヘルパ（例: `kakeibo.sql.run_query("monthly_summary.sql", year_month=...)`）。
- 固定フィクスチャ（手計算可能な少量データ）と期待結果 DataFrame の比較テスト。

### 含まない

- 残高推移（Phase 3.3 / Phase 4.4 で別クエリを作成）。
- カテゴリ階層のロールアップ（親カテゴリへの集計、Phase 3.4 で扱う）。
- UI 表示用フォーマット（Phase 3 の責務）。
- インデックス最適化（実データ規模で問題が出てから対応）。

## 依存タスク

- `worker/docs/plans/Ph1/07-ingest-cli.md`（Phase 1.6 取込CLI: 集計対象となる `transactions` レコードを生成する手段）。

## 後続タスク

- Phase 3.3 月次推移グラフ（本プラン群の対象外、`01-development-plan.md` §4.3 で扱う）。
- Phase 4.4 残高整合性レポート（本プラン群の対象外）。
- Phase 4.5 Obsidian 月次サマリ出力（本プラン群の対象外）。

## 対象ファイル/モジュール

| パス | 役割 |
|---|---|
| `postgres/src/sql/queries/monthly_summary.sql` | 月次サマリ SQL 本体 |
| `shared/kakeibo_shared/sql/__init__.py` | SQL ファイル読込ヘルパ（共通：api / worker から再利用） |
| `shared/kakeibo_shared/sql/runner.py` | `run_query(filename, **params)` の実装 |
| `tests/fixtures/sql/monthly_summary_seed.sql` | テスト用フィクスチャ（小量サンプル取引、リポジトリルートの横断 fixture） |
| `tests/fixtures/sql/monthly_summary_expected.json` | 期待される集計結果 |
| `postgres/tests/sql/test_monthly_summary.py` | クエリ実行 + 期待結果比較 |

## 実装方針

1. **SQL 構造**:
   ```sql
   SELECT
       date_trunc('month', occurred_on)::date AS month,
       COALESCE(c.name, 'その他') AS category_name,
       SUM(CASE WHEN t.amount < 0 THEN -t.amount ELSE 0 END) AS expense,
       SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END) AS income,
       COUNT(*) AS tx_count
   FROM transactions t
   LEFT JOIN categories c ON c.id = t.category_id
   WHERE occurred_on >= :date_from AND occurred_on < :date_to
   GROUP BY 1, 2
   ORDER BY 1, 2;
   ```
2. **パラメータ**: `:date_from`, `:date_to`（両端の含む / 含まないを境界として明確化、`[from, to)` 半開区間）。
3. **未分類取引**: `LEFT JOIN` + `COALESCE(c.name, 'その他')` で取りこぼしを防ぐ。
4. **金額の符号**: 出金は負値で格納されているため、`-t.amount` で正の支出額に戻す。
5. **runner ヘルパ**: `pathlib.Path(__file__).parent.parent.parent / "sql" / "queries" / filename` で SQL を読み込み、`psycopg.cursor.execute(sql, params)` で実行。`params` は `dict[str, Any]`、SQL 内では `%(date_from)s` 形式で展開（psycopg 規約）。あるいは `:name` 形式の場合は SQLAlchemy の `text()` を使う。
6. **テストフィクスチャ**: `monthly_summary_seed.sql` で `institutions` / `accounts` / `categories` / `transactions` を 5〜10 件投入。期待結果は `expected.json` に手計算で記載。
7. **比較**: `pytest` 内でクエリ結果（`list[dict]`）と `expected.json` を `Decimal` 精度で比較。`json.loads` 時は `parse_float=Decimal` で読み込む。

## 受入条件

- サンプルデータ投入後、`monthly_summary.sql` の出力が手計算（`expected.json`）と完全一致する（Decimal 精度で比較）。
- カテゴリ未分類の取引（`category_id IS NULL`）も `その他` として集計に含まれる。
- pytest からクエリを呼び出して値を検証できる（テストが緑）。
- 期間境界（月初 0:00 / 翌月 1 日 0:00）が `[from, to)` 半開区間として正しく扱われる。
- `pyright` クリーン、`ruff` 違反なし。

## テスト計画

### ユニットテスト（テスト先行）

1. **基本集計**: 5〜10 件のサンプル取引を投入し、月別 × カテゴリ別の集計が `expected.json` と一致。
2. **未分類取引**: `category_id = NULL` の取引が `その他` カテゴリに集計される。
3. **期間境界**: 月末 23:59 と翌月 0:00 の取引が、それぞれ正しい月にカウントされる。
4. **空期間**: 取引のない期間を渡すと空リスト（または件数 0 行）が返る。
5. **複数月**: 2 か月にまたがるデータで、月ごとに正しく分割される。

### TDD アプローチ

- Red: フィクスチャ + `expected.json` を準備し、`runner.run_query("monthly_summary.sql", ...)` 未実装でテストを落とす。
- Green: `runner.py` と SQL を最小実装して 1 件目のテストを通す → 順次他のケースを通す。
- Refactor: SQL を CTE で読みやすくする / runner のキャッシュ機構を入れる。

## 想定 issue タイトル / ブランチ名

- 想定 issue タイトル: `Phase 1.8: 月次サマリ SQL の実装と手計算一致検証`
- ブランチ名: `feature/monthly-summary-sql`
- ベースブランチ: `develop`
