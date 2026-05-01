---
title: worker/04 SMBC CSV アダプタ
service: worker
phase_task_id: 1.5
priority: 中
source_plan: docs/plans/06-phase1-smbc-csv-adapter.md
branch: feature/adapter-smbc-csv
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/04 SMBC CSV アダプタ（Phase 1.5）

## このファイルの位置付け

原典 `docs/plans/06-phase1-smbc-csv-adapter.md` を `worker` サービス担当の指示書として再編。原典との乖離時は原典優先。

## 担当サービス

`worker` コンテナ。`src/kakeibo/adapters/smbc.py` + SMBC 用ゴールデンマスタ fixture。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `worker/02`（IngestAdapter ABC） |
| 下流 | `worker/05`（取込CLI） |

`worker/03 (MUFG)` と並行可能。`worker/03` を参考実装として参照する。

## 入力

1. **原典**: `docs/plans/06-phase1-smbc-csv-adapter.md`（必読）
2. **アダプタ設計**: `worker/docs/design/02-ingest-adapters.md`
3. **ADR**: `docs/adr/001-hybrid-ingestion-strategy.md`, `docs/adr/007-adapter-pattern.md`
4. **参考**: `worker/03-mufg-csv-adapter.md`（独立実装だが書き方の参考に）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `src/kakeibo/adapters/smbc.py` | `SmbcCsvAdapter` 実装 |
| `tests/fixtures/smbc/sample.csv` | SMBC 合成データ |
| `tests/fixtures/smbc/expected.json` | 期待 Transaction リスト |
| `tests/unit/adapters/test_smbc.py` | ゴールデンマスタ + 列差分検証 + 摘要正規化 |

## 実装方針（原典 §実装方針より要約）

1. **クラス**: `SmbcCsvAdapter(IngestAdapter)`。`source: ClassVar[str] = "smbc"`。`parse(self, payload: bytes) -> Iterable[Transaction]`。
2. **エンコーディング**: SMBC は UTF-8 / Shift_JIS のいずれか **固定**。実 CSV を確認して fixtures に反映（自動判定は不可、`R-08`）。
3. **列マッピング**: SMBC 列名（`年月日`, `お引出し`, `お預入れ`, `お取り扱い内容`, `残高` など）を定数化。MUFG とは別の列名であることを明示。
4. **摘要正規化**: 全角スペース → 半角スペース or 削除、全角ハイフン → 半角ハイフンなどを `_normalize_description(s: str) -> str` として実装。**Phase 1.7（worker/06）と整合させる**。
5. **金額符号**: お引出し → 負、お預入れ → 正（MUFG と同じ思想）。
6. **ハッシュ**: 共通 `compute_hash`。MUFG と同じ呼び出し方式（`self.account_id` 注入）。
7. **MUFG との独立性**: テスト内で「MUFG の sample.csv を SMBC アダプタに渡すと `ColumnMissingError`」を 1 件記述。

## 実装手順（TDD）

### 1. Red

- `tests/fixtures/smbc/sample.csv` を SMBC フォーマットで合成（5〜10 行）。
- `tests/fixtures/smbc/expected.json` に期待 Transaction を記述。
- `tests/unit/adapters/test_smbc.py` で次を網羅：
  - ゴールデンマスタ完全一致
  - MUFG sample を渡すと `ColumnMissingError`（独立性確認）
  - 摘要正規化の単体テスト（全角スペース除去 / 全角ハイフン → 半角）
  - 金額符号（引出 / 預入それぞれ）
  - 同一 CSV 2 回パースでハッシュ一致

### 2. Green

- 最小実装からゴールデンマスタ全件を通す。
- `_normalize_description` を最初は素朴な `replace` チェーンで実装。
- MUFG との共通化は **しない**。

### 3. Refactor

- 列名定数の整理。共通化を急がない（原典 §実装方針 §Refactor の指針：意図的に重複を残し、Phase 2 以降で必要が固まってから抽出）。

## 受入条件

- サンプル CSV から `expected.json` の N 件が抽出される
- MUFG sample を渡すと `ColumnMissingError`（独立性）
- 摘要正規化が適用された結果でハッシュが決定的
- お引出し → 負、お預入れ → 正
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
pytest tests/unit/adapters/test_smbc.py
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/adapter-smbc-csv`
- コミット粒度（最低 4 件）：
  1. `テスト: SMBC CSVゴールデンマスタとMUFG入力での独立性確認テストを先行作成`
  2. `機能: SmbcCsvAdapter本体（列マッピング・摘要正規化）を実装`
  3. `機能: 引出/預入の符号正規化と例外ハンドリングを追加`
  4. `テスト: 摘要正規化の単体テストとハッシュ決定性テストを追加`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 1.5 SMBC CSV アダプタを実装。

## 成果物
- src/kakeibo/adapters/smbc.py
- tests/fixtures/smbc/{sample.csv, expected.json}
- tests/unit/adapters/test_smbc.py

## 検証結果
- pytest tests/unit/adapters/test_smbc.py: 全件緑
- pyright / ruff: クリーン

## 次のアクション提案
worker/03 と worker/04 が揃った時点で worker/05 (取込CLI) に進む。
```

## 注意事項

- **chardet 等の自動判定は使用禁止**（`R-08`）。
- MUFG アダプタとの共通化は **行わない**。Phase 1 では別実装で十分（早すぎる抽象化禁止）。
- 摘要正規化のルールは `worker/06`（ハッシュ境界条件 PBT）と整合する形で固定する。
- ゴールデンマスタの合成データに実取引情報を含めない。
