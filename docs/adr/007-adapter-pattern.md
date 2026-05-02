---
adr: 007
title: 機関別取込ロジックをアダプタパターンに統一
status: 採用済み
date: 2026-04-30
author: 池田遼介
related:
  - ADR-001
  - ADR-006
---

# ADR-007: 機関別取込ロジックをアダプタパターンに統一

## ステータス
採用済み

## 背景

本アプリケーションは設計書 §1.3 / §5.1 のとおり 11 機関から取り込みを行い、それぞれ以下のように原本フォーマットが異なる。

- 三菱UFJ銀行: Shift_JIS CSV
- 三井住友銀行: CSV
- ひふみ投信: PDF + CSV
- 楽天証券: CSV（投資信託・株式・米国株で別画面）
- Amazon / 楽天 / Yahoo!: HTML / Plain メール
- PayPay: アプリ出力 CSV
- PayPal: 公式 API JSON

入力フォーマット・文字コード・列名・日付フォーマットがすべて異なるため、機関別の解釈ロジックを切り出す抽象化が必要。さらに将来の新規機関追加（楽天銀行など）の影響を局所化したい。

## 検討した選択肢

### 選択肢A. 機関別の関数群（フラットなモジュール）
- メリット: 最も単純、追加が一関数で済む
- デメリット: 共通インターフェースを強制できず、テスト構造が機関ごとにバラバラになる。新規開発者がパターンを把握しにくい

### 選択肢B. `IngestAdapter` 抽象基底クラス（ABC）
- メリット: `parse()` / `extract_holdings()` のシグネチャを強制。テストはアダプタごとにゴールデンマスタテストで統一可能（設計書 §5.2）。新規機関追加時の影響範囲が adapters/ 配下に局所化
- デメリット: 抽象クラス越しの呼び出しでわずかに記述が冗長になる

### 選択肢C. DSL（YAML/JSON で列マッピング定義）
- メリット: 設定駆動でアダプタ追加がコード変更なしに行える
- デメリット: PDF パース、HTML メール解析、文字コード差異、複数ファイル統合（楽天証券の 3 画面 CSV）等、宣言的に書き切れないケースが多すぎる。DSL の表現力を上げると結局コードを書くことになる

## 決定

選択肢 B を採用する。設計書 §5.2 のとおり以下のインターフェースに統一する。

```python
class IngestAdapter(ABC):
    source: str
    @abstractmethod
    def parse(self, payload) -> Iterable[Transaction]: ...
    @abstractmethod
    def extract_holdings(self, payload) -> Iterable[Holding]: ...
```

各機関で 1 ファイル（`adapters/mufg.py` など）。テストは `tests/fixtures/<機関>/` にサンプル原本を配置し、ゴールデンマスタテストで実装する。

## 理由

- 11 機関のフォーマットの異質さは DSL では吸収しきれず、コードで書き切るのが現実的
- ABC で `parse` / `extract_holdings` のシグネチャを強制することで、新規機関追加時の TODO が機械的に明確になる
- ゴールデンマスタテスト（agent-rules/11-testing-strategy.md と整合）はアダプタ単位が最も書きやすく、リグレッション検出力が高い
- アダプタ層の純粋性（DB アクセスなし、副作用なし）を保つことで、TDD（agent-rules/00-core-principles.md）と相性が良い

## 結果

- ディレクトリ構造: `worker/adapters/{base.py, mufg.py, smbc.py, ...}` の構成が確定
- 共通の `Transaction` / `Holding` データクラスを `adapters/types.py` に定義
- アダプタは「原本（payload）→ 共通型」の純粋変換関数として実装し、DB 書き込みは別レイヤ（`Reconciler` 等）が担う（設計書 §3.1, §3.2）
- 新規機関追加の手順がドキュメント化しやすくなる: 「(1) サンプル原本を fixtures に配置 → (2) ゴールデンマスタテストを書く → (3) アダプタ実装 → (4) 機関マスタに登録」

### Phase 1.3 確定事項（2026-05-02 追記）

Phase 1.3「IngestAdapter ABC」実装時に以下 4 点を確定した。`worker/docs/design/02-ingest-adapters.md` §2.1〜2.2 の旧記述（`account_key` / `extract_holdings` デフォルト実装 / `Payload` に `Path` を含む / `extract_balance` 言及）とは Phase 1.2 共通型確定後の最新合意で乖離しているため、以下を本 ADR で唯一の正規仕様とする。design/02 本体の整合更新は別 Phase で対応。

1. **コンストラクタ注入で `account_id: int` を保持**
   - シグネチャ: `__init__(self, *, account_id: int)`（keyword-only 必須）
   - `parse(payload)` / `extract_holdings(payload)` の引数は `payload` のみ。可変引数や `**context` 拡張は採用しない
   - 理由: 「アダプタ = 1 口座にバインド」を契約として固定し、Phase 1.4 / 1.5 機関別実装の均質化を優先

2. **`Payload` 型を `bytes | str | dict[str, Any]` で固定**
   - design/02 §2.1 の `Path` を含む Union から変更
   - CSV はファイル読込後の `bytes`、メールは `str` / `bytes`、API は `dict` で全機関を吸収
   - 理由: ファイル読込責務は呼出側（Phase 1.6 取込 CLI）に分離。アダプタは「I/O なしの純粋変換」を維持

3. **`extract_holdings` を `@abstractmethod` 化**
   - design/02 §2.1 のデフォルト実装案（`return iter(())`）から変更
   - 各サブクラスで `return iter(())` を明示させる
   - 理由: 「holdings 未対応」を暗黙化しない、型安全性とコードレビュー時の意図確認を担保

4. **`source: ClassVar[str]` を `__init_subclass__` で検証**
   - 未設定 / 非 `str` / 空文字列・空白のみはクラス定義時に `TypeError`（``value.strip() == ""`` で whitespace-only も弾く）
   - `cls.__dict__` 直参照で「サブクラス自身が定義したか」を厳密判定（親 `ClassVar` 宣言だけで誤通過させない）
   - 理由: アダプタ登録ミスを実行直前ではなくロード時に検出する Fail Fast

公開範囲: `worker/src/kakeibo_worker/adapters/__init__.py` からの `IngestAdapter` re-export は本 Phase では行わない。Phase 1.4 で `ADAPTER_REGISTRY` 導入時にパブリック API 設計を併せて再判断する。

例外型（`AdapterError` 等）は本 Phase では宣言せず、Phase 1.4 で MUFG CSV アダプタが実際に raise する箇所を実装するときに同タスク内で導入する（YAGNI）。
