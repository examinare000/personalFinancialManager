---
title: ui/Ph3/04 ポートフォリオ構成ビュー
service: ui
phase_task_id: 3.5
priority: 中
source_plan: docs/plans/01-development-plan.md
source_section: §4.3 Phase 3.5（行 357-365）
branch: feature/portfolio-view
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# ui/Ph3/04 ポートフォリオ構成ビュー（Phase 3.5）

## このファイルの位置付け

原典 §4.3 Phase 3.5 を `ui` サービス担当の指示書として展開。`holdings` から銘柄種別ごとの構成比を **円グラフ**で表示し、評価額 NULL の銘柄を警告アイコン付きで列挙する。

## 担当サービス

`compose.yml` `ui` サービス。`ui/app/portfolio/` にポートフォリオページを追加。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `ui/Ph3/01`（雛形）+ `api/Ph3/02`（`/api/holdings/composition`） |
| 下流 | `ui/Ph3/06`（Playwright e2e） |

`ui/Ph3/02 / 03 / 05` と並列着手可能。

## 入力

1. **原典**: `docs/plans/01-development-plan.md` §4.3 Phase 3.5（行 357-365）
2. **データモデル**: `postgres/docs/design/01-data-model.md`（`holdings` の `symbol_kind`, `balance_snapshots`）
3. **API 仕様**: `api/Ph3/02-aggregation-endpoints.md` の `/api/holdings/composition`
4. **既存資産**: `ui/Ph3/01` の基盤、`src/kakeibo/domain/holding.py` の `SymbolKind` 列挙（Phase 1.2）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `ui/lib/api/portfolio.ts` | `useHoldingComposition()` |
| `ui/lib/portfolio/composition.ts` | 構成比計算・NULL 警告分離（純関数） |
| `ui/components/charts/PortfolioPieChart.tsx` | recharts `PieChart`（Client Component） |
| `ui/components/portfolio/HoldingWarnings.tsx` | 評価額 NULL 銘柄リスト |
| `ui/components/portfolio/SnapshotDate.tsx` | 直近スナップショット日付表示 |
| `ui/app/portfolio/page.tsx` | ポートフォリオページ |
| 各 `__tests__/` | 構成比計算 + 警告 + 空状態 |

## 実装方針

1. **構成比計算は API + UI 双方でテスト**: API 側で計算済みだが、UI 側のロジック（％表示・色割当）は単体テスト対象（`composition.ts`）。
2. **NULL 銘柄**: 別領域に列挙、警告アイコン + 「最終取得日: YYYY-MM-DD」表示。`/api/holdings/composition` の `warnings` フィールドをそのまま展開。
3. **`symbol_kind` の表記**: `src/kakeibo/domain/holding.py` の `SymbolKind`（`stock` / `fund` / `etf` / `crypto` / `cash`）と整合。日本語表示は `stock` → `株式` のような変換を `ui/lib/portfolio/labels.ts` に集約。
4. **色割当**: `symbol_kind` 別に固定色（再描画で色が変わらないよう `colors[symbol_kind]` で参照）。`recharts` の自動配色は使わない。
5. **Server / Client Component**: `page.tsx` は Server、`PieChart` は `"use client"`。

## 実装手順（TDD）

### 1. Red

- `composition.test.ts`：
  - `test_calculates_total_value_excluding_nulls()`
  - `test_separates_null_value_holdings_into_warnings()`
  - `test_ratio_sums_to_one_excluding_nulls()`
  - `test_handles_empty_holdings()`
- `PortfolioPieChart.test.tsx`：
  - `test_renders_pie_segments_per_symbol_kind()`
  - `test_pie_chart_has_accessible_label()`
  - `test_segment_colors_consistent_across_renders()`
- `HoldingWarnings.test.tsx`：
  - `test_lists_null_value_holdings_with_last_seen()`
  - `test_empty_when_no_warnings()`
- `page.test.tsx`：
  - `test_snapshot_date_displayed()`
  - `test_empty_state_when_no_holdings()`

### 2. Green

1. `ui/lib/portfolio/composition.ts`（純関数）を実装
2. `ui/lib/portfolio/labels.ts` で `symbol_kind` → 日本語ラベル変換
3. `ui/lib/api/portfolio.ts` で `useHoldingComposition` 実装
4. `ui/components/charts/PortfolioPieChart.tsx` を実装
5. `ui/components/portfolio/{HoldingWarnings,SnapshotDate}.tsx` を実装
6. `ui/app/portfolio/page.tsx` で統合

### 3. Refactor

- `composition.ts` を純関数で完全に切り離し（テスト容易性）
- 色定義を `ui/lib/theme/portfolio-colors.ts` に集約

## 受入条件

原典 §4.3 Phase 3.5 受入基準：
- `symbol_kind` 別構成比が表示
- 評価額 NULL の銘柄は警告アイコン付きで列挙
- 直近スナップショット日付が画面に明示

加えて：
- 評価額合計と各セグメントの合計が一致
- スナップショット日付が「YYYY年MM月DD日」形式
- `symbol_kind` 別の色が一貫（再描画で色変わらない）
- 構成比 % の小数 1 桁表示（端数誤差調整は最大セグメントに寄せる）
- `tsc --strict` クリーン

## 品質ゲート

```bash
cd ui
npm run test -- portfolio
npm run typecheck
npm run lint
```

## ブランチ・コミット規約

- ブランチ: `feature/portfolio-view`
- コミット粒度（最低 4 件）：
  1. `テスト: ポートフォリオ円グラフ・構成比計算・NULL警告のテストを先行作成`
  2. `機能: 構成比計算ロジック（純関数）を実装`
  3. `機能: PortfolioPieChart と警告コンポーネントを実装`
  4. `機能: portfolio ページにスナップショット日付とビューを統合`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 3.5 ポートフォリオ構成ビューを実装。

## 成果物
- ui/lib/api/portfolio.ts
- ui/lib/portfolio/{composition,labels}.ts
- ui/components/charts/PortfolioPieChart.tsx
- ui/components/portfolio/{HoldingWarnings,SnapshotDate}.tsx
- ui/app/portfolio/page.tsx
- 各 __tests__/

## 検証結果
- npm run test / typecheck / lint: 全件緑
- 構成比合計 = 100%（NULL除外）

## 次のアクション提案
ui/Ph3/02 / 03 / 05 と並行可能、すべて完了で ui/Ph3/06 へ。
```

## 注意事項

- **`symbol_kind` の文字列定義**: `src/kakeibo/domain/holding.py` と一致させる（Coder は当該ファイルを Read）。
- **NULL 警告の最終取得日**: API から返る `last_seen` をそのまま表示、UI で計算しない。
- **円グラフのラベル**: 大きいセグメント（10% 以上）はチャート内、小さいセグメントは凡例に逃がす（`recharts` の `Label` プロパティ調整）。
- **アクセシビリティ**: 円グラフは視覚情報のみだと読み上げられないので、隣接して銘柄種別 / 金額 / 構成比のテーブルを併設（`role="img"` + `aria-label` + 詳細はテーブル）。
