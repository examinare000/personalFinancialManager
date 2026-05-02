---
adr: 018
title: Python ドメインオブジェクトの実装方針（dataclass の採用）
status: 採用済み
date: 2026-05-02
author: Gemini-cli
related:
  - ADR-014
  - ADR-015
---

# ADR-018: Python ドメインオブジェクトの実装方針（dataclass の採用）

## ステータス
採用済み

## 背景

Phase 1 において、各取込アダプタ（`worker`）の出力を統一し、DB 永続化層（`postgres`）へ渡すための共通ドメインオブジェクト（`Transaction`, `Holding`, `BalanceSnapshot`）が必要である。これらの実装方針について、保守性・型安全・パフォーマンスの観点から決定する必要がある。

## 検討した選択肢

### 選択肢A. 手書きの Class / dict
- メリット: 外部依存ゼロ。
- デメリット: ボイラープレート（`__init__`, `__repr__` 等）が多く、バリデーションロジックが分散しやすい。

### 選択肢B. Pydantic (v2)
- メリット: 強力なバリデーション、シリアライズ機能、IDE 連携。
- デメリット: 依存関係が増える。起動速度やメモリ効率において dataclass に劣る（大規模データ時）。

### 選択肢C. Standard Library `dataclass`（採用）
- メリット: 標準ライブラリのため依存ゼロ。`frozen=True`, `slots=True` による不変性とメモリ効率の確保。
- デメリット: 複雑なバリデーションには `__post_init__` の手書きが必要。

## 決定

選択肢 C を採用する。

- `shared/kakeibo_shared/domain/` 配下に `dataclass(frozen=True, slots=True)` として定義する。
- 必須バリデーション（金額の `Decimal` 型強制、通貨コードのバリデーション等）は `__post_init__` で実装する。
- Pydantic の導入は Phase 3（Flask API での JSON スキーマ検証が必要になる段階）まで延期し、Phase 1 ではコア層の軽量さを優先する。

## 理由

- Phase 1 の主なタスクは大量の取引データの取込であり、実行時オーバーヘッドが少なく、依存関係が最小限な標準 dataclass が適している。
- `frozen=True` によりドメインオブジェクトの不変性を担保し、副作用によるバグを防止する。
- `slots=True`（Python 3.10+）により、大量のオブジェクトをメモリ上に保持する際の効率を向上させる。

## 結果

- `Transaction`, `Holding`, `BalanceSnapshot` が `kakeibo_shared` に実装され、全サービスの共通言語となる。
- `Decimal` を用いた厳密な金額計算（ADR-005）がコードレベルで強制される。
