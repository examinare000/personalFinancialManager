---
title: Phase 1.4 MUFG CSV アダプタ
phase: 1
task_id: 1.4
status: Draft
priority: 中
parent: docs/plans/01-development-plan.md
last_updated: 2026-04-30
---

# Phase 1.4 MUFG CSV アダプタ

## タスク概要

三菱UFJ銀行（MUFG）の **Shift_JIS CSV** を `Transaction` に正規化する `MufgCsvAdapter` を実装する。`IngestAdapter` 契約（Phase 1.3）に準拠し、ゴールデンマスタテストで決定的な抽出結果を保証する。Phase1 のクリティカルパス上で、Phase 1.6 取込CLI が依存する。

参照: `docs/plans/01-development-plan.md` §4.1 Phase 1.4, §3.1 完了条件 (b)（冪等性）, `worker/docs/design/02-ingest-adapters.md`, リスク R-08（文字コード固定）。

## 目的・背景

### 目的

- MUFG の CSV を Shift_JIS で読み込み、各行を `Transaction` に変換する。
- 出金行は `amount` 負、入金行は `amount` 正で生成し、後段の集計で符号を意識せず合算できるようにする。
- 同じ CSV 行を再パースしてもハッシュが一致し（`compute_hash` 経由）、CLI 段で UNIQUE 違反として冪等に弾かれる前提を作る。

### 背景

- MUFG の出力 CSV は文字コードが Shift_JIS で固定されており（リスク R-08 の暫定方針）、UTF-8 として読むと文字化け → 摘要ベースのハッシュが破綻する。
- 銀行 API 直結が不可（ADR-002）、スクレイピング不採用（ADR-003）のため、CSV 取込が唯一の取得経路（ADR-001 ハイブリッド方式）。
- `01-development-plan.md` §4.1 Phase 1.5（SMBC）と並行可能だが、CLI（Phase 1.6）が両方を必要とするため、本タスクと SMBC は同時期に完了する必要がある。

## スコープ

### 含む

- `MufgCsvAdapter(IngestAdapter)` の実装（`source = "mufg"`）。
- Shift_JIS デコード処理。デコード失敗時の明示的例外。
- 列マッピング（日付 / 摘要 / 出金額 / 入金額 / 残高 / 取引区分など、MUFG CSV の実フォーマットに合わせる）。
- 出金額カラム → 負値、入金額カラム → 正値への正規化。
- ゴールデンマスタテスト用サンプル CSV（`tests/fixtures/mufg/sample.csv` 等、合成データを Shift_JIS で配置）。
- ハッシュ生成は共通の `compute_hash` を呼び、本アダプタ内で再実装しない。

### 含まない

- DB 永続化（Phase 1.6 取込CLI の責務）。
- 実 MUFG 口座のスクレイピング・ログイン自動化（ADR-003 で禁止）。
- SMBC（Phase 1.5）との CSV 共通化リファクタ（差分が固まってから別ブランチで実施）。
- ファイル監視（Phase 2.1 Watcher）。

## 依存タスク

- `04-phase1-ingest-adapter-base.md`（Phase 1.3 IngestAdapter ABC）。

## 後続タスク

- `07-phase1-ingest-cli.md`（Phase 1.6 取込CLI: 本アダプタを呼び出して DB 永続化）。

## 対象ファイル/モジュール

| パス | 役割 |
|---|---|
| `worker/src/kakeibo_worker/adapters/mufg.py` | `MufgCsvAdapter` 実装 |
| `worker/src/kakeibo_worker/adapters/errors.py` | `EncodingMismatchError`, `ColumnMissingError`（Phase 1.3 で雛形定義済の場合は追記） |
| `tests/fixtures/mufg/sample.csv` | Shift_JIS のゴールデンマスタ（合成データ） |
| `tests/fixtures/mufg/expected.json` | 期待される `Transaction` リスト（フィールドのスナップショット） |
| `tests/fixtures/mufg/broken_encoding.csv` | エラーパス用（UTF-8 として作成） |
| `worker/tests/unit/adapters/test_mufg.py` | ゴールデンマスタテスト + エラーパステスト |

## 実装方針

1. **`MufgCsvAdapter` クラス**: `IngestAdapter` を継承、`source: ClassVar[str] = "mufg"` を宣言。コンストラクタは ABC 由来の `__init__(self, *, account_id: int)` をそのまま利用し、追加の引数は取らない（`04-phase1-ingest-adapter-base.md` の契約に従う）。`parse(payload: bytes) -> Iterable[Transaction]` を実装し、`account_id` は `self.account_id` から参照する。`extract_holdings` は空のイテラブルを返す。
2. **デコード**: `payload.decode("shift_jis")` を `try/except UnicodeDecodeError` で囲み、失敗時は `EncodingMismatchError` を送出。chardet 等の自動判定は **使わない**（リスク R-08 の方針）。
3. **CSV 解析**: `csv.DictReader` で行イテレーション。MUFG の実フォーマットの列名（例: `日付`, `摘要`, `お支払金額`, `お預り金額`, `差引残高`）を定数化。列が欠損していたら `ColumnMissingError`。
4. **金額正規化**: 出金額カラムが空でない場合 `amount = -Decimal(value.replace(",", ""))`、入金額カラムが空でない場合 `amount = Decimal(value.replace(",", ""))`。両方空 / 両方ある行は不正データとして例外。
5. **日付**: `datetime.strptime(row["日付"], "%Y/%m/%d").date()`。年が 2 桁表記の場合は別フォーマットを試行（実 CSV を確認後、フィクスチャに反映）。
6. **`description` 正規化**: 前後の全角・半角空白除去は **行わない**（ADR-006 の境界条件は Phase 1.7 で確定）。摘要をそのまま採用。
7. **ハッシュ**: `compute_hash(account_id, occurred_on, amount, description)` を呼ぶ。`account_id` は ABC のコンストラクタで注入された `self.account_id` を参照する（`04-phase1-ingest-adapter-base.md` で確定済の契約）。`parse` 引数で `account_id` を受け取る、または `parse(payload, **context)` への拡張は採用しない。CLI（Phase 1.6）は `MufgCsvAdapter(account_id=...)` でインスタンス化してから `parse(payload)` を呼ぶ。
8. **ゴールデンマスタ**: `tests/fixtures/mufg/sample.csv` に Shift_JIS で 5〜10 行の合成データを置き、`expected.json` と照合。

## 受入条件

- サンプル CSV（Shift_JIS）から既知の N 件（`expected.json` に定義）の `Transaction` が抽出される（フィールド完全一致）。
- 出金行は `amount` 負、入金行は `amount` 正。
- `broken_encoding.csv`（UTF-8）を渡すと `EncodingMismatchError` が送出される。
- 同一 CSV を再パースしても、生成される `Transaction.hash` が前回と一致する（決定性）。
- 列が欠損している壊れた CSV で `ColumnMissingError` が送出される。
- `pyright` クリーン、`ruff` 違反なし。

## テスト計画

### ユニットテスト（テスト先行）

1. **ゴールデンマスタテスト**: `sample.csv` をパースし、`expected.json` と完全一致を比較（`Transaction` を `dataclasses.asdict` で dict 化、Decimal は文字列で比較）。
2. **符号正規化**: 出金 / 入金それぞれ専用の最小 CSV（1 行）を渡し、`amount` の符号を確認。
3. **エンコーディング不一致**: UTF-8 で書いた CSV を渡し、`EncodingMismatchError` を `pytest.raises` で確認。
4. **列欠損**: 必須列を 1 つ抜いた CSV で `ColumnMissingError`。
5. **数値パース不能**: 出金額に `"abc"` が入った行で `ValueError`（または専用例外）。
6. **ハッシュ決定性**: 同じ CSV を 2 回 parse し、生成された `Transaction` リストの `hash` 列が完全一致。

### TDD アプローチ

- Red: `tests/fixtures/mufg/sample.csv` と `expected.json` を作り、`MufgCsvAdapter` 未実装の状態でテストを書いて落とす。
- Green: 最小実装で 1 件抽出から始め、徐々にゴールデンマスタ全件を通す。
- Refactor: 列名定数 / 金額正規化ロジックを関数抽出。

## 想定 issue タイトル / ブランチ名

- 想定 issue タイトル: `Phase 1.4: MUFG CSV 取込アダプタの実装`
- ブランチ名: `feature/adapter-mufg-csv`
- ベースブランチ: `develop`
