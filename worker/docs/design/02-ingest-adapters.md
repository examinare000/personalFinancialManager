---
title: 取込アダプタ詳細設計
version: 1.0
status: Draft
last_updated: 2026-05-01
related_adrs:
  - ADR-001
  - ADR-007
  - ADR-018
---

# 取込アダプタ詳細設計

## 1. 概要

本ドキュメントは、各金融機関・ECサービスからのデータ取込ロジックを統一的に扱う「アダプタパターン」（ADR-007）の詳細設計を示す。概要設計 §5 を土台とし、共通インターフェース、機関別アダプタ仕様、テスト方針、新規機関の追加手順を実装可能なレベルで定義する。

ハイブリッド取得方式（ADR-001）に従い、CSV / PDF / メール / API / 手動入力 の5系統の入力源を、すべて同じ `IngestAdapter` インターフェースに収束させる。

## 2. 共通インターフェース

### 2.1 IngestAdapter ABC

```python
# worker/src/kakeibo_worker/adapters/base.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Union

from .types import Transaction, Holding

Payload = Union[Path, str, bytes, dict]


class IngestAdapter(ABC):
    """機関別取込ロジックの共通インターフェース。

    すべての取込ロジックはこの ABC を実装する。アダプタは入力（payload）を
    受け取り、共通スキーマである Transaction / Holding を yield する責務のみを持つ。
    DBへの書き込みやカテゴリ分類はアダプタの責務外。
    """

    source: str  # 機関コード (例: 'mufg', 'rakuten_sec')
    encoding: str = "utf-8"

    @abstractmethod
    def parse(self, payload: Payload) -> Iterable[Transaction]:
        """取引明細をパースする。payloadはアダプタごとに型が異なる。"""

    def extract_holdings(self, payload: Payload) -> Iterable[Holding]:
        """保有資産を抽出する。実装は任意（残高が取得不可なソースは未実装）。"""
        return iter(())

    def extract_balance(self, payload: Payload) -> "Iterable[BalanceSnapshot]":
        """日次残高を抽出する。実装は任意。"""
        return iter(())
```

### 2.2 共通型

```python
# shared/kakeibo_shared/domain/{transaction,holding,balance_snapshot}.py（dataclass を分割配置）
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional


@dataclass(frozen=True, slots=True)
class Transaction:
    account_key: str            # (institution, account_no) を識別する文字列
    occurred_on: date
    amount: Decimal             # 入金正、出金負
    description: str
    occurred_at: Optional[datetime] = None
    counterparty: Optional[str] = None
    currency: str = "JPY"
    raw_payload: dict[str, Any] = field(default_factory=dict)
    source_file: Optional[str] = None
    hash: Optional[str] = None  # ADR-017 に基づき算出


@dataclass(frozen=True, slots=True)
class Holding:
    account_key: str
    symbol: str
    symbol_kind: str            # 'cash','stock','fund','crypto','bond'
    quantity: Decimal
    as_of: date
    market_value: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BalanceSnapshot:
    account_key: str
    as_of: date
    balance: Decimal
    source: str = "csv"
```

`Decimal` を必ず使う（float禁止、ADR-005）。`account_key` はアダプタ層では文字列で扱い、永続化層に渡る前にDBの `accounts.id` へ解決する。

## 3. 機関別アダプタ仕様

### 3.1 三菱UFJ銀行 (MufgCsvAdapter)

| 項目 | 内容 |
|---|---|
| 入力フォーマット | Shift_JIS CSV（`三菱UFJ_明細_YYYYMMDD.csv`） |
| 文字コード | `cp932` |
| 列マッピング | 日付→`occurred_on`、`摘要 + 摘要内容`→`description`（空白連結 + `rstrip()`、hash 衝突回避目的）、支払い金額→`amount`（負）、預かり金額→`amount`（正）、差引残高→balance_snapshot |
| 残高抽出 | 可（行ごとに残高列あり） |
| 留意点 | ダイレクトでの履歴保持期間が短く、月初までに必須DL |
| テストフィクスチャ | `tests/fixtures/mufg/sample_001.csv` |

### 3.2 三井住友銀行 (SmbcCsvAdapter)

| 項目 | 内容 |
|---|---|
| 入力フォーマット | UTF-8 BOM付きCSV |
| 文字コード | `utf-8-sig` |
| 列マッピング | 年月日→`occurred_on`、お引出し→出金、お預入れ→入金、お取り扱い内容→`description` |
| 残高抽出 | 可 |
| 留意点 | ヘッダ行が複数行（口座情報メタ）。スキップ処理必須 |
| テストフィクスチャ | `tests/fixtures/smbc/sample_001.csv` |

### 3.3 三井住友信託銀行 (SmtbCsvAdapter)

| 項目 | 内容 |
|---|---|
| 入力フォーマット | CSV（月次） |
| 文字コード | `cp932` |
| 列マッピング | 取引日→`occurred_on`、摘要→`description`、金額（出金/入金分離） |
| 残高抽出 | 可 |
| 留意点 | 履歴保持90日、月次バッチ厳守 |
| テストフィクスチャ | `tests/fixtures/smtb/sample_001.csv` |

### 3.4 ひふみ投信 (HifumiPdfAdapter)

| 項目 | 内容 |
|---|---|
| 入力フォーマット | PDF月次レポート + 取引履歴CSV |
| 文字コード | PDF: pypdfで抽出、CSV: utf-8 |
| 列マッピング | 取引日→`occurred_on`、約定金額→`amount`、口数→`quantity` |
| 残高抽出 | PDFから保有口数・基準価額を抽出 |
| 留意点 | PDFレイアウトが年に数回変わるためゴールデンマスタ必須 |
| テストフィクスチャ | `tests/fixtures/hifumi/report_2026_03.pdf` |

### 3.5 楽天証券 (RakutenSecCsvAdapter)

| 項目 | 内容 |
|---|---|
| 入力フォーマット | CSV（投資信託・国内株式・米国株で別画面・別ファイル） |
| 文字コード | `cp932` |
| 列マッピング | 約定日→`occurred_on`、銘柄→`symbol`、数量→`quantity`、約定単価→`unit_cost` |
| 残高抽出 | 可（保有商品一覧） |
| 留意点 | 米国株は通貨USD。`currency='USD'` 設定 |
| テストフィクスチャ | `tests/fixtures/rakuten_sec/{fund,jp_stock,us_stock}_001.csv` |

### 3.6 SMBC日興証券 (SmbcNikkoCsvAdapter)

| 項目 | 内容 |
|---|---|
| 入力フォーマット | CSV（日興イージートレード） |
| 文字コード | `cp932` |
| 列マッピング | 受渡日→`occurred_on`、銘柄→`symbol`、約定金額→`amount` |
| 残高抽出 | 可 |
| 留意点 | 月次取込、特定口座/一般口座の区別あり（`raw_payload` に保持） |
| テストフィクスチャ | `tests/fixtures/smbc_nikko/sample_001.csv` |

### 3.7 Amazon (AmazonMailAdapter)

| 項目 | 内容 |
|---|---|
| 入力フォーマット | 注文確認メール（HTML/Plain） |
| 文字コード | UTF-8 |
| 列マッピング | 注文番号→`raw_payload.order_id`、合計金額→`amount`（負）、注文日→`occurred_on` |
| 残高抽出 | 不可 |
| 留意点 | デジタル/物販で本文形式が異なる。複数アイテム合算で1取引 |
| テストフィクスチャ | `tests/fixtures/amazon/order_*.eml` |

### 3.8 楽天市場 (RakutenIchibaMailAdapter)

| 項目 | 内容 |
|---|---|
| 入力フォーマット | 注文確認メール（HTML） |
| 文字コード | UTF-8 |
| 列マッピング | 注文番号、店舗名→`counterparty`、合計→`amount`、注文日→`occurred_on` |
| 残高抽出 | 不可 |
| 留意点 | 店舗ごとにメールテンプレが異なる。共通ヘッダから抽出 |
| テストフィクスチャ | `tests/fixtures/rakuten_ichiba/order_*.eml` |

### 3.9 Yahoo!ショッピング (YahooShoppingMailAdapter)

| 項目 | 内容 |
|---|---|
| 入力フォーマット | 注文確認メール（HTML） |
| 文字コード | UTF-8 |
| 列マッピング | 注文番号、合計、注文日 |
| 残高抽出 | 不可 |
| 留意点 | PayPay残高払いとの紐付けは Reconciler で処理 |
| テストフィクスチャ | `tests/fixtures/yahoo_shopping/order_*.eml` |

### 3.10 PayPay (PayPayCsvAdapter)

| 項目 | 内容 |
|---|---|
| 入力フォーマット | アプリのCSV出力 |
| 文字コード | UTF-8 |
| 列マッピング | 取引日時→`occurred_at`、加盟店→`counterparty`、金額→`amount` |
| 残高抽出 | 可（残高欄） |
| 留意点 | アプリ→AirDrop or NAS共有→`/inbox/paypay/` |
| テストフィクスチャ | `tests/fixtures/paypay/sample_001.csv` |

### 3.11 PayPal (PayPalApiAdapter)

| 項目 | 内容 |
|---|---|
| 入力フォーマット | Transactions API v1 のJSONレスポンス |
| 文字コード | UTF-8 |
| 列マッピング | `transaction_info.transaction_initiation_date`→`occurred_at`、`transaction_amount.value`→`amount` |
| 残高抽出 | 可（balance API） |
| 留意点 | OAuth2、サンドボックス→本番のキー切替あり。タイムスタンプはISO 8601 |
| テストフィクスチャ | `tests/fixtures/paypal/transactions_2026_04.json` |

## 4. ゴールデンマスタテスト方針

各アダプタについて、入力（fixture）と期待出力（snapshot）を保持してリグレッション検出する。

### 4.1 ディレクトリ構成

```
tests/                            # リポジトリルート横断 fixture（ADR-014）
  fixtures/
    mufg/
      sample_001.csv
      sample_001.expected.json
    smbc/
      sample_001.csv
      sample_001.expected.json
    ...
worker/tests/                     # worker サービス専有テスト本体
  unit/
    adapters/
      test_mufg.py
      test_smbc.py
      ...
```

### 4.2 テストパターン

```python
# worker/tests/unit/adapters/test_mufg.py
import json
from decimal import Decimal
from pathlib import Path

import pytest

from kakeibo_worker.adapters.mufg import MufgCsvAdapter

# 横断 fixture（リポジトリルート tests/fixtures/mufg/）を解決
FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "mufg"


@pytest.mark.parametrize("name", ["sample_001"])
def test_mufg_golden_master(name: str) -> None:
    adapter = MufgCsvAdapter()
    actual = [tx.__dict__ for tx in adapter.parse(FIXTURES / f"{name}.csv")]
    expected = json.loads((FIXTURES / f"{name}.expected.json").read_text())
    # Decimal の文字列比較
    for a, e in zip(actual, expected):
        assert str(a["amount"]) == e["amount"]
        assert a["occurred_on"].isoformat() == e["occurred_on"]
        assert a["description"] == e["description"]
```

期待出力JSONは初回実装時に手動で正解データを作成し、リポジトリにコミットする。アダプタ改修時にdiffで影響範囲が見える。

### 4.3 エッジケース必須項目

各アダプタで以下のフィクスチャを最低限揃える：

- 通常取引（入金・出金各1件以上）
- 残高ゼロを跨ぐ取引
- 同日複数取引
- 摘要に特殊文字（`,`、`"`、改行）を含む取引
- 月跨ぎ取引
- 文字コード境界ケース（機種依存文字）

## 5. 新規機関の追加手順

1. **ADR起草**: 取得方式（CSV/メール/API）と判断根拠をADRに残す（必要であれば）。
2. **フィクスチャ作成**: `tests/fixtures/{code}/sample_001.{csv,eml,json}` に実データのサニタイズ済みサンプルを配置。
3. **テスト先行**: `worker/tests/unit/adapters/test_{code}.py` で期待動作をassert（TDD、t-wada推奨）。
4. **アダプタ実装**: `worker/src/kakeibo_worker/adapters/{code}.py` で `IngestAdapter` を実装。
5. **登録**: `worker/src/kakeibo_worker/adapters/__init__.py` の `ADAPTER_REGISTRY` に登録。Watcherがファイル名 / メール送信元から該当アダプタを選択する。
6. **マスタ投入**: `institutions` テーブルに機関を追加するマイグレーション。
7. **動作確認**: 実データ1ヶ月分を `/inbox/` に投下し、全件正しくINSERTされることを確認。

## 6. 既知の課題・申し送り

- メール系アダプタ（Amazon/楽天/Yahoo!）は本文HTMLの変更に弱い。Phase 2 でテンプレ変更検知（パース失敗時の通知）を実装。
- ひふみPDFはレイアウト変更時にパース失敗する想定。失敗時はメール通知して手動入力にフォールバック。
- PayPalタイムゾーンはUTCで返るため、`occurred_on` 算出時に `Asia/Tokyo` へ変換する。
- 文字コード自動判定（chardet）は使わない。機関ごとにencodingを固定し、誤判定を防ぐ。
