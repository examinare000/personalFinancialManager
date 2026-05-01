---
title: worker/02 IngestAdapter ABC（取込アダプタ抽象基底）
service: worker
phase_task_id: 1.3
priority: 高
source_plan: docs/plans/04-phase1-ingest-adapter-base.md
branch: feature/ingest-adapter-base
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/02 IngestAdapter ABC（Phase 1.3）

## このファイルの位置付け

原典 `docs/plans/04-phase1-ingest-adapter-base.md` を `worker` サービス担当の指示書として再編。原典との乖離時は原典優先。

## 担当サービス

`worker` コンテナ。`src/kakeibo/adapters/` 配下の抽象基底 + 共通エラー型。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `worker/01`（共通型） |
| 下流 | `worker/03`（MUFG）, `worker/04`（SMBC）, Phase2 系メール / API アダプタ |

## 入力

1. **原典**: `docs/plans/04-phase1-ingest-adapter-base.md`（必読）
2. **アダプタ設計**: `worker/docs/design/02-ingest-adapters.md`
3. **ADR**: `docs/adr/007-adapter-pattern.md`
4. **依存型**: `src/kakeibo/domain/`（`worker/01` 完了後の状態）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `src/kakeibo/adapters/__init__.py` | 公開 API（`IngestAdapter`, `AdapterError` など） |
| `src/kakeibo/adapters/base.py` | `IngestAdapter` ABC + `__init_subclass__` での `source` 検証 |
| `src/kakeibo/adapters/errors.py` | `AdapterError` 基底 + `EncodingMismatchError`, `ColumnMissingError` 雛形 |
| `tests/unit/adapters/__init__.py` | 新規 |
| `tests/unit/adapters/_dummy_adapter.py` | テスト専用ダミーアダプタ |
| `tests/unit/adapters/test_base.py` | 契約検証 |

## 実装方針（原典 §実装方針より要約）

1. **ABC 定義**: `IngestAdapter(abc.ABC)`。`__init__(self, *, account_id: int)` は ABC 側で具体実装、`self.account_id = account_id`。
2. **抽象メソッド**: `parse(self, payload) -> Iterable[Transaction]` と `extract_holdings(self, payload) -> Iterable[Holding]`。`payload: bytes | str | dict[str, Any]` Union。
3. **`source` 強制**: `__init_subclass__(cls, **kwargs)` で `cls.source` の存在と非空文字列を検証。未設定なら `TypeError`。`source: ClassVar[str]` を ABC に宣言。
4. **`account_id` 注入**: コンストラクタ経由のみ。`parse` 引数に `account_id` を含める / `**context` 拡張は **採用しない**。
5. **エラー型**: `AdapterError(Exception)` を基底に、`EncodingMismatchError`, `ColumnMissingError` を派生。Phase 1.4/1.5 で送出。
6. **ダミーアダプタ**: テスト fixture 用。`source = "dummy"`、`parse(payload)` が固定 Transaction を返す。

## 実装手順（TDD）

### 1. Red

`tests/unit/adapters/test_base.py` に以下を記述：
- 抽象メソッド未実装サブクラスの初期化が `TypeError`
- `source` 未設定サブクラス定義時に `TypeError`（クラス定義時点で発生）
- `DummyAdapter()`（`account_id` なし）が `TypeError`、`DummyAdapter(account_id=42).account_id == 42`
- `DummyAdapter(account_id=42).parse(b"")` が `Iterable[Transaction]` を返し各要素が `Transaction` で `account_id == 42`
- `extract_holdings(b"")` が空イテラブル

`from kakeibo.adapters.base import IngestAdapter` で ImportError → 落ちることを確認。

### 2. Green

- `src/kakeibo/adapters/errors.py` を最小実装。
- `src/kakeibo/adapters/base.py` で `IngestAdapter` を実装。`__init_subclass__` 内で `cls.source` 検証。
- `tests/unit/adapters/_dummy_adapter.py` を実装。
- 各テストを順に通す。

### 3. Refactor

- `__init_subclass__` 内のバリデーションを `_validate_source(cls)` に抽出可能か検討。

## 受入条件

- `IngestAdapter.__init__(self, *, account_id: int)` を備える
- `parse` / `extract_holdings` が抽象メソッド
- `source` 未設定サブクラスは初期化前（クラス定義時）に `TypeError`
- 抽象メソッド未実装サブクラスのインスタンス化が `TypeError`（Python 標準 `abc` 挙動）
- `account_id` キーワード引数なしで初期化すると `TypeError`
- ダミーアダプタが契約を満たす
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
pytest tests/unit/adapters/    # 全件緑
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/ingest-adapter-base`
- コミット粒度（最低 4 件）：
  1. `テスト: IngestAdapter契約とsource属性必須化のテストを先行作成`
  2. `機能: AdapterError基底とEncodingMismatchError/ColumnMissingError雛形を追加`
  3. `機能: IngestAdapter ABCとaccount_id注入・source強制を実装`
  4. `テスト: テスト用ダミーアダプタを追加`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 1.3 IngestAdapter ABC を実装。

## 成果物
- src/kakeibo/adapters/{base.py, errors.py, __init__.py}
- tests/unit/adapters/{test_base.py, _dummy_adapter.py}

## 検証結果
- pytest tests/unit/adapters/: 全件緑
- pyright / ruff: クリーン

## 次のアクション提案
worker/03 (MUFG) と worker/04 (SMBC) を並列着手可能。
```

## 注意事項

- `extract_holdings` は銀行アダプタには無関係だが、抽象を保ち各サブクラスで `return ()` を明示する設計を採用（型安全性）。
- `parse(payload, **context)` のような可変引数注入や `parse(payload, account_id=...)` は **採用禁止**。`account_id` はインスタンス属性経由（原典 §実装方針 3）。
- `payload` 型 Union に dict を含めることで Phase 2 系のメール / API レスポンスにも対応。
