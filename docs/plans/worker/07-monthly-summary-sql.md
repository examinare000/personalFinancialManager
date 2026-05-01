---
title: worker/07 月次サマリ SQL
service: worker
phase_task_id: 1.8
priority: 中
source_plan: docs/plans/09-phase1-monthly-summary-sql.md
branch: feature/monthly-summary-sql
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/07 月次サマリ SQL（Phase 1.8）

## このファイルの位置付け

原典 `docs/plans/09-phase1-monthly-summary-sql.md` を `worker` サービス担当の指示書として再編。原典との乖離時は原典優先。Phase1 完了条件 (c)「SQL で月次サマリが手計算と一致」を直接満たす。

## 担当サービス

`worker` コンテナ。`sql/queries/monthly_summary.sql`（クエリ本体）と `src/kakeibo/sql/runner.py`（アプリ層からの呼び出しヘルパ）。クエリ本体は `postgres` サービスのスキーマを前提とするが、ファイル・テストは `worker` 帰属。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `worker/05`（取込CLI: 集計対象データを生成する手段） |
| 下流 | Phase 3.3 月次推移グラフ、Phase 4.5 Obsidian 月次出力（本プラン群対象外） |

`worker/06` と並行可能。

## 入力

1. **原典**: `docs/plans/09-phase1-monthly-summary-sql.md`（必読）
2. **データモデル**: `postgres/docs/design/01-data-model.md`
3. **ADR**: `docs/adr/004-postgres-jsonb.md`
4. **既存スキーマ**: `postgres/01` 完了後の `transactions` / `categories` テーブル
5. **既存資産**: `sql/queries/.gitkeep`（プレースホルダ）、`pyproject.toml` の `psycopg`, `sqlalchemy` 依存

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `sql/queries/monthly_summary.sql` | 月次サマリ SQL 本体 |
| `src/kakeibo/sql/__init__.py` | パッケージ初期化（公開 API: `run_query`） |
| `src/kakeibo/sql/runner.py` | `run_query(filename, **params)` 実装 |
| `tests/fixtures/sql/monthly_summary_seed.sql` | テスト用フィクスチャ（institutions / accounts / categories / transactions の少量サンプル） |
| `tests/fixtures/sql/monthly_summary_expected.json` | 期待集計結果（手計算） |
| `tests/unit/sql/__init__.py` | 新規 |
| `tests/unit/sql/test_monthly_summary.py` | クエリ実行 + 期待結果比較 |

## 実装方針（原典 §実装方針より要約）

### SQL 構造

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

### 設計上のポイント

1. **パラメータ**: `:date_from`（含む）, `:date_to`（含まない）の半開区間。
2. **未分類取引**: `LEFT JOIN` + `COALESCE(c.name, 'その他')` で取りこぼし防止。
3. **金額符号**: 出金は負値で格納されているので `-t.amount` で正の支出額。
4. **runner ヘルパ**: `pathlib.Path(__file__).parent.parent.parent / "sql" / "queries" / filename` で SQL を読み込む。`SQLAlchemy text()` で `:name` バインディングを使う（`psycopg` 経由でも `sqlalchemy.text` 経由でも整合）。
5. **テストフィクスチャ**: `monthly_summary_seed.sql` で 5〜10 件投入。期待値は `expected.json` に手計算で記載。`json.loads(parse_float=Decimal)` で読み込む。
6. **比較**: `Decimal` 精度で完全一致比較。

## 実装手順（TDD）

### 1. Red

- `tests/fixtures/sql/monthly_summary_seed.sql` で institutions / accounts / categories / transactions を 2 か月分・5〜10 件投入。
- `tests/fixtures/sql/monthly_summary_expected.json` に期待集計結果を手計算で記述（`Decimal` 精度）。
- `tests/unit/sql/test_monthly_summary.py` で次を網羅：
  - 基本集計（全件一致）
  - 未分類取引が `その他` に集計
  - 期間境界（月末 vs 翌月 1 日）
  - 空期間で空リスト
  - 複数月で月ごとに正しく分割
- `runner.run_query(...)` 未実装で全件落ちることを確認。

### 2. Green

- `src/kakeibo/sql/runner.py` で `run_query(filename: str, *, engine: Engine, **params)` を最小実装。
- `sql/queries/monthly_summary.sql` を上記構造で実装。
- 各テストを順に通す。

### 3. Refactor

- SQL を CTE で読みやすくする。
- runner にファイル読込のキャッシュ機構を入れる（必要時のみ）。

## 受入条件

- サンプルデータ投入後、SQL 出力が `expected.json` と Decimal 精度で完全一致
- カテゴリ未分類取引（`category_id IS NULL`）が `その他` に集計
- pytest からクエリを呼び出して値検証可能
- 期間境界 `[from, to)` の半開区間で正しく動作
- 複数月データで月ごとに分割
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
pytest tests/unit/sql/         # 全件緑（testcontainers 起動含む）
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/monthly-summary-sql`
- コミット粒度（最低 4 件）：
  1. `テスト: 月次サマリの基本集計・未分類・期間境界テストを先行作成`
  2. `機能: SQLファイル読込ヘルパとrun_queryランナーを実装`
  3. `機能: 月次サマリSQLクエリ本体を実装`
  4. `テスト: フィクスチャ（投入データ + 期待結果JSON）を追加`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 1.8 月次サマリ SQL を実装。

## 成果物
- sql/queries/monthly_summary.sql
- src/kakeibo/sql/{__init__.py, runner.py}
- tests/fixtures/sql/{monthly_summary_seed.sql, monthly_summary_expected.json}
- tests/unit/sql/test_monthly_summary.py

## 検証結果
- pytest tests/unit/sql/: 全件緑
- 月次サマリが手計算と完全一致（Decimal精度）
- pyright / ruff: クリーン

## 既知の課題・申し送り
（あれば）

## 次のアクション提案
Phase1 完了条件 (a) (b) (c) (d) すべて達成。Phase 2 着手準備が整った。
```

## 注意事項

- 期間は **半開区間 `[from, to)`** を採用（`>= :date_from AND < :date_to`）。月末 23:59:59 / 翌月 0:00 のグレーゾーンを排除。
- `expected.json` の `Decimal` は `json.loads(parse_float=Decimal)` で読み込み、`float` 経由で精度を失わせない。
- フィクスチャの投入データに **実取引情報を含めない**（合成データのみ）。
- インデックス最適化は本タスクでは不要（実データ規模で問題が顕在化してから対応、原典 §スコープ「含まない」）。
- 本クエリは Phase 3.3 / Phase 4.5 で再利用される前提。`sql/queries/` 配下に独立配置することで再利用性を担保（ハードコードしない）。
