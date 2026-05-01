---
title: Phase 1.5 SMBC CSV アダプタ
phase: 1
task_id: 1.5
status: Draft
priority: 中
parent: docs/plans/01-development-plan.md
last_updated: 2026-04-30
---

# Phase 1.5 SMBC CSV アダプタ

## タスク概要

三井住友銀行（SMBC）の CSV を `Transaction` に正規化する `SmbcCsvAdapter` を実装する。`IngestAdapter` 契約（Phase 1.3）に準拠し、MUFG アダプタ（Phase 1.4）と独立して動作する。MUFG とは列順・列名・摘要正規化の差分が想定されるため、本タスクで SMBC 固有の振る舞いを切り分ける。

参照: `docs/plans/01-development-plan.md` §4.1 Phase 1.5, `worker/docs/design/02-ingest-adapters.md`。

## 目的・背景

### 目的

- SMBC の CSV を読み込み、各行を `Transaction` に変換する。
- MUFG とは別の列順・列名でも、同じ `IngestAdapter` 契約を満たすことを実証する。
- SMBC 特有の摘要表記（全角スペース・全角記号など）の正規化方針を決定し、ハッシュ生成への影響を最小化する。

### 背景

- 銀行ごとに CSV のフォーマットが大きく異なるため、共通化を急ぐと壊れやすい抽象化になる。各機関ごとに専用アダプタを用意する方針（ADR-007）。
- SMBC の出力 CSV はエンコーディングが UTF-8 または Shift_JIS のいずれかである可能性があるため、実 CSV を確認して固定する（リスク R-08 と同様の方針：自動判定は使わない）。
- Phase 1.4（MUFG）と並行作業可能（`01-development-plan.md` §4.1 Phase 1.5 の依存欄）。CLI（Phase 1.6）が両方を呼ぶため、両アダプタが揃った段階で次に進む。

## スコープ

### 含む

- `SmbcCsvAdapter(IngestAdapter)` の実装（`source = "smbc"`）。
- SMBC 固有の列順・列名へのマッピング（実フォーマットを fixtures に固定）。
- 摘要の全角スペース除去等の SMBC 固有正規化（必要なら）。
- ゴールデンマスタテスト用サンプル CSV と期待結果。

### 含まない

- MUFG アダプタ（Phase 1.4）と SMBC アダプタの抽象化リファクタ。Phase 1 の段階では別実装で十分（早すぎる抽象化を避ける）。
- DB 永続化（Phase 1.6）。
- ファイル監視・ディレクトリ振り分け（Phase 2.1 / 2.2）。

## 依存タスク

- `04-phase1-ingest-adapter-base.md`（Phase 1.3 IngestAdapter ABC）。
- `05-phase1-mufg-csv-adapter.md`（Phase 1.4）とは独立で並行可能だが、参考実装として参照する。

## 後続タスク

- `07-phase1-ingest-cli.md`（Phase 1.6 取込CLI: 本アダプタを呼び出して DB 永続化）。

## 対象ファイル/モジュール

| パス | 役割 |
|---|---|
| `worker/src/kakeibo_worker/adapters/smbc.py` | `SmbcCsvAdapter` 実装 |
| `tests/fixtures/smbc/sample.csv` | SMBC ゴールデンマスタ（合成データ） |
| `tests/fixtures/smbc/expected.json` | 期待される `Transaction` リスト |
| `worker/tests/unit/adapters/test_smbc.py` | ゴールデンマスタ + 列差分検証 + 摘要正規化テスト |

## 実装方針

1. **`SmbcCsvAdapter` クラス**: `IngestAdapter` を継承、`source: ClassVar[str] = "smbc"`。`parse(payload: bytes) -> Iterable[Transaction]`。
2. **列マッピング**: SMBC の列名（例: `年月日`, `お引出し`, `お預入れ`, `お取り扱い内容`, `残高`）を定数化。MUFG とは別の列名であることを明示する。
3. **摘要正規化**: 全角スペース → 半角スペース or 削除、全角ハイフン → 半角ハイフン等の正規化を `_normalize_description(s: str) -> str` として実装。Phase 1.7 のハッシュ境界条件テストと整合させる。
4. **金額符号**: MUFG と同様、お引出し → 負、お預入れ → 正。
5. **ハッシュ生成**: 共通 `compute_hash` を呼ぶ。`account_id` の渡し方は MUFG と同じ方式を採用（Phase 1.4 で決定した方式に揃える）。
6. **MUFG との差分明示**: テスト内で「MUFG の `expected.json` を SMBC アダプタに渡しても抽出できない」等の独立性チェックを 1 件入れる（列名が異なるため失敗する）。

## 受入条件

- サンプル CSV から `expected.json` に定義された既知の N 件が抽出される。
- MUFG アダプタとは独立して `IngestAdapter` 契約を満たす（`source = "smbc"`、抽象メソッドが実装済み）。
- 列順・列名差分が MUFG と区別される（MUFG の sample.csv を本アダプタに渡すと `ColumnMissingError`）。
- SMBC 特有の摘要正規化が適用された結果でハッシュが決定的に同一になる。
- `pyright` クリーン、`ruff` 違反なし。

## テスト計画

### ユニットテスト（テスト先行）

1. **ゴールデンマスタテスト**: `sample.csv` → `expected.json` 完全一致。
2. **MUFG 入力での失敗確認**: MUFG の sample を SMBC アダプタに渡して `ColumnMissingError` 発生（独立性の証明）。
3. **摘要正規化**: 全角スペースありの摘要 / なしの摘要が同一の正規化済み文字列になることを確認（`_normalize_description` の単体テスト）。
4. **金額符号**: 引出 / 預入それぞれの最小ケース。
5. **ハッシュ決定性**: 同一 CSV の 2 回パースで `Transaction.hash` 一致。

### TDD アプローチ

- Red: `tests/fixtures/smbc/sample.csv` と `expected.json` を作り、`SmbcCsvAdapter` 未実装でテストを落とす。
- Green: 最小実装からゴールデンマスタ全件を通す。
- Refactor: 共通になりそうな部分は anti-pattern を避けて意図的に重複を残し、Phase 2 以降で必要が確定してから抽出。

## 想定 issue タイトル / ブランチ名

- 想定 issue タイトル: `Phase 1.5: SMBC CSV 取込アダプタの実装`
- ブランチ名: `feature/adapter-smbc-csv`
- ベースブランチ: `develop`
