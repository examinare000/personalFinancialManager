---
title: postgres サービス Phase2 タスク指示書
service: postgres
phase: 2
status: NoTasks
parent_index: docs/plans/12-phase2-service-assignments.md
last_updated: 2026-05-01
---

# postgres サービス Phase2 タスク指示書

## 結論：Phase2 では本サービス向けの新規実装タスクなし

`compose.yml` `postgres` サービス（PostgreSQL 16-alpine）は Phase 1.1（`postgres/Ph1/01-schema-migrations.md`）でスキーマが確定する設計。Phase 2 ではメール取込（Amazon / 楽天 / Yahoo）と PayPal API 取込を `transactions` テーブルに **正規化済みの形で投入** するため、**スキーマ変更は発生しない**。

`docs/plans/01-development-plan.md` §4.2 のタスク 2.1〜2.8 をすべて確認しても、DB スキーマを拡張する項目はない。

## サービス境界（参考）

| 範囲 | パス | Phase 2 での扱い |
|---|---|---|
| Alembic マイグレーション本体 | `alembic/versions/0001〜0005_*.py` | **追加・変更なし** |
| `transactions.raw_payload` JSONB | DB スキーマ | 既存定義のまま、メール / PayPal の生データもここに格納 |
| ENUM `category_source` | DB スキーマ | 既存値 `('rule','llm','manual')` のまま使用 |
| バックアップサービス | `compose.yml` `backup` | 既存の `pg_dump` 日次運用で十分 |

## Phase2 の間に postgres サービスへ波及する変更（許容例）

| 変更例 | 受入可否 | 備考 |
|---|---|---|
| `compose.yml` `postgres` 環境変数の変更 | 不要 | – |
| `postgres` ヘルスチェックの変更 | 不要 | – |
| `transactions.raw_payload` のキー命名規約の合意 | 推奨（指示書レベルで完結） | Amazon/楽天/Yahoo/PayPal で共通の JSON キー命名（例: `order_id`, `transaction_id`, `points_used`）を `worker/Ph2/04〜07` の各指示書で固定済み |

`agent-rules/00-core-principles.md` 絶対遵守の3原則 §1 デグレッション防止に従い、**既存スキーマと既存テスト（`tests/unit/db/`）を壊さない** ことを最優先する。

## Phase 4 への申し送り

Phase 4 で本サービスに変更が必要となる候補：

- LLM 分類結果の専用フィールド追加（`category_source='llm'` の確信度・モデル名等を `raw_payload` に乗せるか専用カラムを追加するかの設計判断、原典 `docs/plans/01-development-plan.md` §4.4 Phase 4.1）
- Reconciler の `linked_tx_id` 列追加（Phase 4.3）
- `categorization_rules` の優先度カラム追加（Phase 3.6 / 4.2）

これらは Phase 4 着手時に `docs/plans/postgres/Ph4/` を新設して扱う。

## 担当 Worker サブエージェント

Phase2 期間中に発生する可能性があるのは **Reviewer のみ**：

| Worker | 役割 |
|---|---|
| Reviewer | `worker/Ph2/03〜07` で `raw_payload` に投入される JSON 構造が、既存 `transactions.raw_payload` の JSONB として problem なく格納されることを Read のみで確認 |
| Reviewer | `worker/Ph2/01〜02` で取込される CSV メタ情報（archive 移動先など）が、既存 `institutions` / `accounts` テーブルの参照整合性を破壊しないことを確認 |

Coder / Planner / Git-composer の起動は Phase2 では原則不要。
