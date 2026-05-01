---
title: worker/06 ハッシュ冪等性ユニットテスト強化
service: worker
phase_task_id: 1.7
priority: 中
source_plan: docs/plans/08-phase1-hash-idempotency-tests.md
branch: feature/hash-idempotency-tests
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/06 ハッシュ冪等性ユニットテスト強化（Phase 1.7）

## このファイルの位置付け

原典 `docs/plans/08-phase1-hash-idempotency-tests.md` を `worker` サービス担当の指示書として再編。原典との乖離時は原典優先。Phase1 完了条件 (b) の保険として機能する。

## 担当サービス

`worker` コンテナ。`compute_hash`（`worker/01` で実装済）の境界条件を property-based test で網羅し、description の前後空白の扱いを **テストで固定** する。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `worker/01`（共通型）, `worker/05`（取込CLI） |
| 下流 | `worker/07`（月次サマリ）以降の集計タスク |

`worker/07` と並行可能。

## 入力

1. **原典**: `docs/plans/08-phase1-hash-idempotency-tests.md`（必読）
2. **ADR**: `docs/adr/006-hash-uniqueness.md`
3. **データモデル**: `postgres/docs/design/01-data-model.md`
4. **既存実装**: `src/kakeibo/domain/transaction.py` の `compute_hash`
5. **依存**: `pyproject.toml` `[project.optional-dependencies].dev` に `hypothesis>=6.100,<7` 宣言済み（追加不要）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `tests/unit/domain/test_hash.py` | hypothesis ベースの property-based test |
| `tests/unit/domain/test_hash_boundary.py` | 境界条件の表駆動テスト |
| `src/kakeibo/domain/transaction.py` | （**変更しない**を初期方針。ただし境界条件で正規化方針を変える場合は ADR-006 改訂と同時に） |

## 実装方針（原典 §実装方針より要約）

### hypothesis 戦略

| 引数 | 戦略 |
|---|---|
| `account_id` | `st.integers(min_value=1, max_value=10**6)` |
| `occurred_on` | `st.dates(min_value=date(2000,1,1), max_value=date(2100,12,31))` |
| `amount` | `st.decimals(min_value=Decimal("-1e9"), max_value=Decimal("1e9"), places=4, allow_nan=False, allow_infinity=False)` |
| `description` | `st.text(min_size=0, max_size=200)` |

### 検証ポイント

1. **決定性**: `@given(...)` で生成した入力に対し、`compute_hash(...) == compute_hash(...)` を毎回確認。
2. **1 引数違いで別ハッシュ**: 4 引数のうち 1 つだけ変えたペアが必ず別ハッシュ（`account_id +1` など）。
3. **大量サンプル衝突ゼロ**: 100 件のランダム入力でハッシュ集合のサイズが 100。
4. **境界条件（表駆動）**:
   - description の前後半角空白差異 → 別ハッシュ（**正規化しない方針** が初期採用、ADR-006 と整合）
   - 全角空白と半角空白 → 別ハッシュ
   - 改行コード（`\r\n` vs `\n`） → 別ハッシュ
   - Unicode NFC / NFD → 別ハッシュ（`unicodedata.normalize` を `compute_hash` に組み込まない方針）
   - 空文字 description の扱い（許容するが衝突しないことを確認）
5. **通貨の扱い**: 現行 `compute_hash` シグネチャに `currency` がないため、「同 description / 異 currency 取引が同ハッシュとなる」ことを **明示的にテスト** し、コメントで「機関ごとに通貨は固定なので account_id で区別される」を残す（ADR-006 改訂は別タスク）。

## 実装手順（TDD）

### 1. Red

- `tests/unit/domain/test_hash.py` を作成し、上記 hypothesis テストを記述。
- `tests/unit/domain/test_hash_boundary.py` で表駆動テスト（空白・改行・Unicode 正規化）。
- `pytest tests/unit/domain/test_hash*.py` で `compute_hash` の現挙動を検証。多くは緑になるはずだが、想定外の衝突があれば赤になる。

### 2. Green

- 原則 `compute_hash` 本体は **変更しない**（Phase 1.2 の確定挙動を尊重）。
- 期待値が異なるテストがあれば、まず原典 `docs/plans/03-phase1-domain-types.md` §実装方針 4 と整合を確認し、テスト側を修正（仕様優先）。
- どうしても本体修正が必要な境界条件が見つかった場合は **ADR-006 改訂タスクを別途起票** し、本タスクで勝手に変更しない。

### 3. Refactor

- テストデータ生成ヘルパ（`_make_args(...)`）を抽出。
- 境界条件テーブルをモジュール定数化。

## 受入条件

- 同一 `(account_id, occurred_on, amount, description)` で同一ハッシュ（hypothesis 100 例以上）
- description の前後空白差異で異なるハッシュ
- 100 件ランダムサンプルで衝突 0
- 1 引数違い 100 例で全件別ハッシュ
- 通貨違いの取引が同ハッシュとなる現状をテストで明示（コメント付き）
- `pyright` クリーン、`ruff` 違反ゼロ
- テスト全件 10 秒以内

## 品質ゲート

```bash
pytest tests/unit/domain/test_hash.py tests/unit/domain/test_hash_boundary.py
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/hash-idempotency-tests`
- コミット粒度（最低 3 件）：
  1. `テスト: hypothesisベースのcompute_hash決定性・1引数違い・衝突ゼロのproperty-based testを追加`
  2. `テスト: 空白・改行・Unicode正規化の境界条件を表駆動で固定`
  3. `テスト: currency引数非対応の現状を明示するテストとコメントを追加`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 1.7 ハッシュ冪等性 property-based test を強化。

## 成果物
- tests/unit/domain/{test_hash.py, test_hash_boundary.py}

## 検証結果
- pytest tests/unit/domain/test_hash*.py: 全件緑（X 秒）
- 100件サンプル衝突: 0件
- pyright / ruff: クリーン

## 既知の課題・申し送り
- compute_hash の currency 非対応は明示的なテストで固定。改訂が必要なら ADR-006 改訂を別タスクで起票。

## 次のアクション提案
worker/07（月次サマリSQL）と統合確認。
```

## 注意事項

- `compute_hash` 本体を **本タスクでは変更しない** が原則。仕様変更が必要なら ADR-006 改訂タスクを起票。
- hypothesis のシード固定（`@settings(deadline=None, max_examples=100)`）でテスト実行時間を 10 秒以内に保つ。
- description の正規化方針（NFC / NFKC / strip）を将来導入する場合、`worker/03` `worker/04` の摘要正規化と整合させる必要がある。本タスクでは「正規化しない」を初期方針。
