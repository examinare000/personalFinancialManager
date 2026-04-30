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
