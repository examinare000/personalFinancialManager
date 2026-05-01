---
title: postgres サービス Phase3 タスク指示書
service: postgres
phase: 3
status: NoTasks
parent_index: docs/plans/13-phase3-service-assignments.md
last_updated: 2026-05-01
---

# postgres サービス Phase3 タスク指示書

## 結論：Phase3 では本サービス向けの新規実装タスクなし

`compose.yml` `postgres` サービスのスキーマは Phase 1.1 で確定済み。Phase 3 は **既存の `transactions` / `categories` / `categorization_rules` / `holdings` / `balance_snapshots` を読み出して REST API 経由で UI に提供する** だけのため、スキーマ変更は発生しない。

`docs/plans/01-development-plan.md` §4.3 のタスク 3.1〜3.6 をすべて確認しても、DB スキーマを拡張する項目はない。

## サービス境界（参考）

| 範囲 | パス | Phase 3 での扱い |
|---|---|---|
| Alembic マイグレーション | `postgres/src/alembic/versions/0001〜0005_*.py` | **追加・変更なし** |
| 月次サマリ SQL（Phase 1.8） | `postgres/src/sql/queries/monthly_summary.sql` | 既存のまま、`api/Ph3/02` から呼び出される |
| 集計 SQL（Phase 3 で追加） | `postgres/src/sql/queries/{monthly_balance_trend,category_spending,portfolio_composition}.sql` | **`api` サービス帰属**（`api/Ph3/02-aggregation-endpoints.md` で実装） |
| バックアップサービス | `compose.yml` `backup` | 既存運用維持 |

## Phase3 の間に postgres サービスへ波及する変更（許容例）

| 変更例 | 受入可否 | 備考 |
|---|---|---|
| インデックス追加 | 不要 | Phase 3 完了後に運用ベンチで遅延が顕在化したら別タスク化 |
| `compose.yml` `postgres` 環境変数の変更 | 不要 | – |
| ヘルスチェック変更 | 不要 | – |
| `transactions.raw_payload` JSONB の利用拡張 | 不要 | API レスポンスでは `raw_payload` を返さない方針（PII リスク、`docs/design/05-security-model.md` §10.2） |

`agent-rules/00-core-principles.md` 絶対遵守の3原則 §1 デグレッション防止に従い、**既存スキーマと既存テスト（`tests/unit/db/`）を壊さない** ことを最優先する。

## Phase 4 への申し送り

Phase 4 で本サービスに変更が必要となる候補：

- LLM 分類結果の専用フィールド追加（Phase 4.1）
- Reconciler の `linked_tx_id` カラム追加（Phase 4.3）
- `categorization_rules` への `is_dismissed` フラグ追加（Phase 4.2 半自動学習で「拒否したら再提案しない」）

これらは Phase 4 着手時に `postgres/docs/plans/Ph4/` を新設して扱う。

## 担当 Worker サブエージェント

Phase3 期間中に発生する可能性があるのは **Reviewer のみ**：

| Worker | 役割 |
|---|---|
| Reviewer | `api/Ph3/02` で追加される集計 SQL（`monthly_balance_trend.sql` 等）が既存スキーマの参照整合性を破壊しないこと、JOIN がパフォーマンス上問題ないことを Read のみで確認 |
| Reviewer | `api/Ph3/01` のリポジトリ層が psycopg のパラメータ化クエリを正しく使い、SQL インジェクション耐性を持つことを確認 |

Coder / Planner / Git-composer の起動は Phase3 では原則不要。
