---
title: Phase 1.7 ハッシュ冪等性ユニットテスト強化
phase: 1
task_id: 1.7
status: Draft
priority: 中
parent: docs/plans/01-development-plan.md
last_updated: 2026-04-30
---

# Phase 1.7 ハッシュ冪等性ユニットテスト強化

## タスク概要

`compute_hash` の **境界条件**を property-based test（hypothesis）で網羅し、ハッシュ衝突・誤マージ・冪等性破綻を検出する。Phase1 完了条件 (b) の保険として機能し、Phase 1.6 取込CLI の冪等性を「同じファイル 2 回投入で行数増えず」よりさらに細かい粒度で保証する。

参照: `docs/plans/01-development-plan.md` §4.1 Phase 1.7, `docs/adr/006-hash-uniqueness.md`, `postgres/docs/design/01-data-model.md`。

## 目的・背景

### 目的

- 同一 `(account_id, occurred_on, amount, description)` から生成されるハッシュが常に一致することを多様な入力で確認する。
- 通貨違いや口座違いで必ず別ハッシュになることを property-based test で検証する。
- description の前後空白差異の扱いについて方針を確定し、テストで固定する（正規化するか、しないか）。
- 100 件規模のサンプルでハッシュ衝突がゼロであることを確認する。

### 背景

- ADR-006 のハッシュ戦略は Phase 1.2 で `compute_hash` として実装されているが、ユニットテストでは決定性の確認のみで境界条件が網羅されていない。
- Phase 1.6 取込CLI の段階で「同じ CSV 2 回投入」レベルの冪等性は確認されるが、CSV を跨いだ同日同額の別取引（実運用で発生）の扱いは未検証。
- 半角・全角空白、改行コード、Unicode 結合文字（NFC / NFD）など、文字コード境界での衝突が後から判明すると、運用初期に二重計上が起きるリスクがある。

## スコープ

### 含む

- hypothesis を導入し、`compute_hash` への入力をランダム生成して以下を検証：
  - 同一入力 → 同一ハッシュ（決定性）。
  - 1 引数違い → 別ハッシュ（衝突確率がほぼゼロ）。
  - 100 件規模のランダム入力で衝突 0。
- description の前後空白差異の扱いを ADR-006 と整合する形で決定し、テストで固定する。
- 通貨違いの場合のハッシュ差異を検証（**現行設計では `compute_hash` の引数に `currency` は含まれていない** ため、`currency` を含めるか、別レイヤーで区別するかをこのタスクで明確化する。設計判断が必要なら ADR-006 改訂を起票し、`docs/plans/01-development-plan.md` §10.3 のアンチパターンに従って本プランで勝手に変更しない）。

### 含まない

- DB 制約の検証（Phase 1.1 で実施済）。
- アダプタ単体での冪等性確認（Phase 1.4 / 1.5 のゴールデンマスタテストで実施済）。
- DB を含む統合テスト（Phase 1.6 で実施済）。
- LLM 分類のハッシュへの影響（Phase 4.1 の責務）。

## 依存タスク

- `03-phase1-domain-types.md`（Phase 1.2 共通型: `compute_hash` の実装が前提）。
- `07-phase1-ingest-cli.md`（Phase 1.6 取込CLI: 実運用の入力データを参考に境界条件を抽出）。

## 後続タスク

- `09-phase1-monthly-summary-sql.md`（Phase 1.8 月次サマリ SQL: 冪等性が保証されてから集計の正確性を検証）。
- Phase 4.4 残高整合性レポート（本プラン群の対象外）が冪等性の保険を活用する。

## 対象ファイル/モジュール

| パス | 役割 |
|---|---|
| `tests/unit/domain/test_hash.py` | property-based test 本体（hypothesis 利用） |
| `tests/unit/domain/test_hash_boundary.py` | 境界条件の表駆動テスト（半角・全角空白、Unicode 正規化等） |
| `pyproject.toml` | 既存・参照のみ。hypothesis は `[project.optional-dependencies].dev` に `"hypothesis>=6.100,<7"` として既に宣言済みのため変更不要（`[tool.uv.dev-dependencies]` セクションは存在しない） |
| `shared/kakeibo_shared/domain/transaction.py` | `compute_hash` 本体（Phase 1.2 で実装済）。本タスクで判明した境界条件に応じて正規化方針を反映する場合のみ変更 |

## 実装方針

1. **hypothesis 戦略の構築**:
   - `account_id`: `st.integers(min_value=1, max_value=10**6)`。
   - `occurred_on`: `st.dates(min_value=date(2000,1,1), max_value=date(2100,12,31))`。
   - `amount`: `st.decimals(min_value=Decimal("-1e9"), max_value=Decimal("1e9"), places=4, allow_nan=False, allow_infinity=False)`。
   - `description`: `st.text(min_size=0, max_size=200)`。
2. **決定性テスト**: `@given(...)` で入力を生成し、`compute_hash(...) == compute_hash(...)` を毎回確認。
3. **1 引数違いテスト**: `@given(...)` で入力を生成し、4 つの引数のうち 1 つだけを変更すると別ハッシュになることを確認。`account_id` を `+1` した場合などをチェック。
4. **大量サンプル衝突ゼロ**: 100 件のランダム入力をセットで生成し、生成されたハッシュ集合のサイズが 100 であること（衝突なし）を確認。
5. **境界条件の表駆動テスト**:
   - description の前後半角空白差異 → 別ハッシュ（正規化しない方針を初期採用、ADR-006 と整合）。
   - 全角空白と半角空白 → 別ハッシュ。
   - 改行コード（\\r\\n vs \\n） → 別ハッシュ。
   - Unicode NFC / NFD → 別ハッシュ（NFC 正規化を後で導入する場合は ADR-006 改訂と本テスト改修を同時に行う）。
6. **通貨の扱い**: 現行 `compute_hash` シグネチャに `currency` がないため、テスト内で「同 description / 異 currency の取引が同ハッシュになる」ことを **問題として明示**するテストを 1 件記述し、Phase 1 の暫定方針として「機関ごとに通貨は固定なので account_id で区別される」ことをコメントで残す（ADR-006 の改訂は別タスク）。

## 受入条件

- 同一 `(account_id, occurred_on, amount, description)` は同一ハッシュ（hypothesis で 100 例以上検証）。
- description の前後空白差異で異なるハッシュ（または明示的に正規化される。本プラン執筆時点では「正規化しない」が初期方針）。
- 通貨が異なる取引で同ハッシュとなる現状を **テストで明示**し、設計上の前提（account_id で区別）をコメントで残す。
- 100 件のランダムサンプルでハッシュ衝突が 0 件。
- 1 引数違いの入力ペアが 100 例とも別ハッシュ。
- `pyright` クリーン、`ruff` 違反なし、テストが 10 秒以内で完了。

## テスト計画

### ユニットテスト（テスト先行）

1. **`test_hash.py`**: hypothesis ベースの property-based test。決定性 + 1 引数違いでの分離 + 衝突ゼロ。
2. **`test_hash_boundary.py`**: 表駆動テストで以下を検証。
   - 半角空白前後差異（"foo" vs " foo "）。
   - 全角空白を含む（"foo　bar" vs "foo bar"）。
   - 改行コード差異。
   - Unicode 結合文字（"が" vs "か" + 濁点）。
   - 空文字 description の扱い。
3. **`test_hash.py` の通貨注記**: 同入力で `currency` だけが違うケースは現行 API では区別されないことを `pytest.mark.xfail` または `assert ==` で明示し、コメントで設計意図を残す。

### TDD アプローチ

- Red: hypothesis 未導入かつ境界テストが書かれていない状態で、新規テストファイルを作成。
- Green: hypothesis を依存に追加し、テストを通す。`compute_hash` の挙動を変更しない（Phase 1.2 で確定済を尊重）。
- Refactor: テストデータ生成ヘルパを抽出。

## 想定 issue タイトル / ブランチ名

- 想定 issue タイトル: `Phase 1.7: ハッシュ冪等性ユニットテストの強化（hypothesis 導入）`
- ブランチ名: `feature/hash-idempotency-tests`
- ベースブランチ: `develop`
