---
adr: 004
title: 永続化基盤にPostgreSQL 16 + JSONBを採用
status: 採用済み
date: 2026-04-30
author: 池田遼介
related:
  - ADR-005
  - ADR-006
---

# ADR-004: 永続化基盤にPostgreSQL 16 + JSONBを採用

## ステータス
採用済み

## 背景

本アプリケーションは設計書 §4 で定義されるとおり、構造化データ（取引・残高・カテゴリ等のリレーショナルなレコード）と、原本データ（機関別 CSV/JSON/メールの生ペイロード）の両方を扱う必要がある。

- 構造化データ: `transactions`, `holdings`, `balance_snapshots`, `categories`, `categorization_rules` など RDB 的な関係を持つ
- 原本データ: パース失敗時の再変換やパーサ改修への耐性のため、`raw_payload` として元データをそのまま保持する必要がある（設計書 §4.3 のデータレイク的発想）

加えて、設計書 §4.2 の DDL に示されるように、`CHECK` 制約による列挙値の整合性検証や、`NUMERIC` による厳密金額計算（→ ADR-005）も必須要件である。

## 検討した選択肢

### 選択肢A. MySQL 8
- メリット: 普及度が高く運用情報が豊富
- デメリット: JSON 型は存在するが JSONB ほどの索引性能はない。NUMERIC は対応するが、CHECK 制約の実装が PostgreSQL より弱い時期があり知見の蓄積で劣る

### 選択肢B. SQLite
- メリット: 単一ファイル、バックアップが容易、Docker レス運用が可能
- デメリット: 厳格な型強制なし（NUMERIC が文字列扱い）、同時書込性能が低い、JSONB 相当の索引なし

### 選択肢C. PostgreSQL 16 + JSONB
- メリット: NUMERIC の厳密精度、JSONB と GIN 索引、CHECK 制約、自己参照外部キー、Docker 公式イメージの普及度、長期運用情報の豊富さ
- デメリット: SQLite と比べ運用要素が増える（コンテナ常駐、バックアップ設計が必要）

### 選択肢D. DocumentDB（MongoDB / Firestore等）
- メリット: 原本ペイロードの保管に親和性が高い
- デメリット: 構造化データの集計・JOIN・整合性制約が弱い。家計簿の分析クエリ（カテゴリ別月次集計、口座横断の時系列）に不向き

## 決定

選択肢 C を採用する。PostgreSQL 16-alpine を Docker Compose 上で常駐させ、構造化テーブルと JSONB の `raw_payload` を併用する（設計書 §7.1）。

## 理由

- 金額計算には `NUMERIC` の厳密精度が必須（ADR-005）であり、SQLite では型強制が緩く採用できない
- 原本保管は JSONB が最適。GIN 索引により後付けでの検索・集計も可能
- 設計書 §4.2 で多用する `CHECK (kind IN (...))` のような列挙制約に対する PostgreSQL の対応が成熟している
- Docker 公式イメージ（`postgres:16-alpine`）が安定しており、自宅 NAS の Docker Compose 運用（→ ADR-009）に乗せやすい
- バックアップは `pg_dump` でテキストダンプを取得でき、3 階層バックアップ（→ ADR-012）と整合する

## 結果

- 全テーブルに JSONB 列を持たせる余地が確保され、パーサ改修時の再処理が可能となる
- ハッシュ UNIQUE による冪等性確保（→ ADR-006）が PostgreSQL の UNIQUE 制約で素直に実装できる
- 運用上、Docker Compose に `postgres` サービスと `backup` サービスを必須要素として組み込む（設計書 §7.1）
- 単一ユーザ規模（月数百件取引）では性能上の問題は発生しない見込み。将来データ量が大きく増えた場合のみパーティショニング検討
