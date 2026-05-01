---
title: worker/03 MUFG CSV アダプタ
service: worker
phase_task_id: 1.4
priority: 中
source_plan: docs/plans/05-phase1-mufg-csv-adapter.md
branch: feature/adapter-mufg-csv
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/03 MUFG CSV アダプタ（Phase 1.4）

## このファイルの位置付け

原典 `docs/plans/05-phase1-mufg-csv-adapter.md` を `worker` サービス担当の指示書として再編。原典との乖離時は原典優先。

## 担当サービス

`worker` コンテナ。`src/kakeibo/adapters/mufg.py` + Shift_JIS ゴールデンマスタ fixture。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `worker/02`（IngestAdapter ABC） |
| 下流 | `worker/05`（取込CLI） |

`worker/04 (SMBC)` と独立並行可能。

## 入力

1. **原典**: `docs/plans/05-phase1-mufg-csv-adapter.md`（必読）
2. **取込フロー**: `worker/docs/design/08-ingest-flow.md`
3. **アダプタ設計**: `worker/docs/design/02-ingest-adapters.md`
4. **ADR**: `docs/adr/001-hybrid-ingestion-strategy.md`, `docs/adr/007-adapter-pattern.md`
5. **リスク**: `docs/plans/01-development-plan.md` §9 R-08（文字コード固定方針）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `src/kakeibo/adapters/mufg.py` | `MufgCsvAdapter` 実装 |
| `src/kakeibo/adapters/errors.py` | 既存ファイルへの追記（`worker/02` で雛形定義済の場合は流用） |
| `tests/fixtures/mufg/sample.csv` | Shift_JIS の合成データ（5〜10 行） |
| `tests/fixtures/mufg/expected.json` | 期待 Transaction リスト（フィールドスナップショット） |
| `tests/fixtures/mufg/broken_encoding.csv` | UTF-8 で書いたエラーパス用 |
| `tests/unit/adapters/test_mufg.py` | ゴールデンマスタ + エラーパス + ハッシュ決定性 |

## 実装方針（原典 §実装方針より要約）

1. **クラス**: `MufgCsvAdapter(IngestAdapter)`。`source: ClassVar[str] = "mufg"`。コンストラクタは ABC 由来 `__init__(self, *, account_id: int)` をそのまま使用。追加引数なし。
2. **デコード**: `payload.decode("shift_jis")` を `try/except UnicodeDecodeError` で囲み、失敗時 `EncodingMismatchError`。**chardet 等の自動判定は使わない**（R-08）。
3. **CSV 解析**: `csv.DictReader` で行イテレーション。MUFG 列名（`日付`, `摘要`, `お支払金額`, `お預り金額`, `差引残高` 等）を定数化。列欠損で `ColumnMissingError`。
4. **金額符号**: 出金カラム → `amount = -Decimal(value.replace(",", ""))`、入金カラム → `amount = Decimal(value.replace(",", ""))`。両方空 / 両方ありは不正。
5. **日付**: `datetime.strptime(row["日付"], "%Y/%m/%d").date()`（実フォーマット要確認、fixture に反映）。
6. **description**: 摘要をそのまま採用（前後空白除去 **しない**。`worker/06` で確定）。
7. **ハッシュ**: 共通 `compute_hash(self.account_id, occurred_on, amount, description)` を呼ぶ。本アダプタ内で再実装禁止。
8. **`extract_holdings`**: 空イテラブル `return ()`。

## 実装手順（TDD）

### 1. Red

- `tests/fixtures/mufg/sample.csv` を Shift_JIS で 5〜10 行作成（合成データ。実取引情報は **入れない**）。
- `tests/fixtures/mufg/expected.json` に期待 Transaction を JSON で記述（`amount` は文字列、`hash` は事前計算した値）。
- `tests/fixtures/mufg/broken_encoding.csv` を UTF-8 で作成。
- `tests/unit/adapters/test_mufg.py` で次を網羅：
  - ゴールデンマスタ完全一致（`dataclasses.asdict` 経由で dict 比較、Decimal は文字列で比較）
  - 出金 / 入金それぞれの符号
  - エンコーディング不一致 → `EncodingMismatchError`
  - 列欠損 → `ColumnMissingError`
  - 数値パース不能 → `ValueError`（or 専用例外）
  - 同一 CSV 2 回パースで `Transaction.hash` 一致

### 2. Green

- `MufgCsvAdapter` を最小実装で 1 件抽出から開始。
- 列マッピング → 符号正規化 → 全件抽出 → エラーパスの順に通す。

### 3. Refactor

- 列名定数 / 金額正規化 (`_normalize_amount`) を private 関数へ抽出。

## 受入条件

- サンプル CSV から `expected.json` の N 件が完全一致で抽出される
- 出金行 `amount` 負、入金行 `amount` 正
- `broken_encoding.csv`（UTF-8）で `EncodingMismatchError`
- 同一 CSV 再パースでハッシュ完全一致
- 列欠損 CSV で `ColumnMissingError`
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
pytest tests/unit/adapters/test_mufg.py
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/adapter-mufg-csv`
- コミット粒度（最低 4 件）：
  1. `テスト: MUFG CSVゴールデンマスタとエラーパスのテストを先行作成`
  2. `機能: MufgCsvAdapter本体（Shift_JISデコード・列マッピング・符号正規化）を実装`
  3. `機能: 数値パース・列欠損・エンコーディング例外ハンドリングを追加`
  4. `テスト: ハッシュ決定性確認テストを追加`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 1.4 MUFG CSV アダプタを実装。

## 成果物
- src/kakeibo/adapters/mufg.py
- tests/fixtures/mufg/{sample.csv, expected.json, broken_encoding.csv}
- tests/unit/adapters/test_mufg.py

## 検証結果
- pytest tests/unit/adapters/test_mufg.py: 全件緑
- pyright / ruff: クリーン

## 次のアクション提案
worker/04 (SMBC) と並行 or 直列で実施 → worker/05 (CLI) へ。
```

## 注意事項

- **chardet 等の自動判定は使用禁止**。Shift_JIS 固定（`R-08`）。
- 摘要の正規化（前後空白 / 全角 → 半角）は **行わない**。Phase 1.7（worker/06）でハッシュ境界条件として確定する。
- ゴールデンマスタの合成データに **実取引情報を含めない**（`agent-rules/12-security-guidelines.md`）。
- SMBC アダプタとの抽象化共通化は **行わない**（早すぎる抽象化を避ける、原典 §スコープ「含まない」）。
