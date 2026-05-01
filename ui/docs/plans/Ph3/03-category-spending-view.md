---
title: ui/Ph3/03 カテゴリ別支出ビュー
service: ui
phase_task_id: 3.4
priority: 中
source_plan: docs/plans/01-development-plan.md
source_section: §4.3 Phase 3.4（行 345-355）
branch: feature/category-spending-view
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# ui/Ph3/03 カテゴリ別支出ビュー（Phase 3.4）

## このファイルの位置付け

原典 §4.3 Phase 3.4 を `ui` サービス担当の指示書として展開。月別カテゴリ別支出を **積み上げ棒グラフ + 表**で表示し、親カテゴリ → 子カテゴリのドリルダウン操作を提供する。

## 担当サービス

`compose.yml` `ui` サービス。`ui/src/app/categories/` にカテゴリ支出ページを追加。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `ui/Ph3/01`（雛形）+ `api/Ph3/02`（`/api/categories/spending`） |
| 下流 | `ui/Ph3/06`（Playwright e2e） |

`ui/Ph3/02 / 04 / 05` と並列着手可能。

## 入力

1. **原典**: `docs/plans/01-development-plan.md` §4.3 Phase 3.4（行 345-355）
2. **分類設計**: `worker/docs/design/03-categorization-engine.md`
3. **ADR**: `docs/adr/008-three-tier-categorization.md`（カテゴリ分類3層戦略）
4. **API 仕様**: `api/Ph3/02-aggregation-endpoints.md` の `/api/categories/spending`
5. **既存資産**: `ui/Ph3/01` の基盤、`ui/Ph3/02` で共通化される `ui/lib/format/currency.ts`

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `ui/lib/api/categories.ts` | `useCategorySpending({month})`, `useCategoryDrilldown({parent_id, month})` |
| `ui/components/charts/CategoryStackedBar.tsx` | 積み上げ棒グラフ（recharts `BarChart` + `Bar` 複数） |
| `ui/components/tables/CategorySpendingTable.tsx` | 表（クリックで子展開） |
| `ui/components/MonthSelector.tsx` | 月選択 |
| `ui/src/app/categories/page.tsx` | カテゴリページ |
| 各 `__tests__/` | Render + ドリルダウン + 未分類表示 |

## 実装方針

1. **ドリルダウン**: 親カテゴリクリックで子カテゴリ展開、`useState` で展開状態管理。子カテゴリは別 API コール（`?parent_id=`）または初回レスポンスに含める（**Planner 推奨：初回レスポンスに `has_children` のみ含め、展開時に追加 API 呼出**でデータ量制御）。
2. **未分類表示**: `category_id === null` を `null_category` キーで API から受領、UI で `未分類` ラベル + 警告色（`agent-rules/15-frontend-design.md` のアクセント色）で強調。
3. **空状態**: データなしの月は `EmptyState`。
4. **金額整形**: `ui/lib/format/currency.ts`（`02` で共通化済）を再利用。
5. **積み上げの安定性**: カテゴリ順序を「金額降順」固定（月ごとに順序が変わらないように親カテゴリ ID で安定ソート）。
6. **Server / Client Component**: `page.tsx` は Server、状態管理を含むテーブル / チャートは `"use client"`。

## 実装手順（TDD）

### 1. Red

- `CategoryStackedBar.test.tsx`:
  - `test_renders_stacked_bar_with_parent_categories()`
  - `test_uncategorized_shown_with_warning_color()`
  - `test_chart_has_accessible_label()`
- `CategorySpendingTable.test.tsx`:
  - `test_clicking_parent_drills_down_to_subcategories()`
  - `test_drilldown_state_resets_on_month_change()`
  - `test_subtotal_matches_parent_amount()`：親合計と子合計が一致
- `page.test.tsx`:
  - `test_month_selector_changes_data()`
  - `test_empty_state_when_no_data()`

### 2. Green

1. `ui/lib/api/categories.ts` で `useCategorySpending` / `useCategoryDrilldown` 実装
2. `ui/components/charts/CategoryStackedBar.tsx` 実装
3. `ui/components/tables/CategorySpendingTable.tsx` 実装（行クリックで子展開）
4. `ui/components/MonthSelector.tsx` 実装
5. `ui/src/app/categories/page.tsx` で統合

### 3. Refactor

- 月選択ロジックを `ui/lib/hooks/useMonthParam.ts` に共通化（`02` の期間フィルタとパターン整合）
- カラーパレットを `ui/lib/theme/category-colors.ts` に集約

## 受入条件

原典 §4.3 Phase 3.4 受入基準：
- 月選択で対象月のカテゴリ別合計が表示
- 親カテゴリでドリルダウン → 子カテゴリ表示
- 未分類取引が `未分類` として可視化

加えて：
- 親展開状態が次の月選択でリセット
- ドリルダウン中に親カテゴリ合計と子カテゴリ合計が一致
- カテゴリ順序が月をまたいで安定（親 ID 順 + 金額降順）
- `tsc --strict` クリーン

## 品質ゲート

```bash
cd ui
npm run test -- categories
npm run typecheck
npm run lint
```

## ブランチ・コミット規約

- ブランチ: `feature/category-spending-view`
- コミット粒度（最低 4 件）：
  1. `テスト: カテゴリ別支出ビュー・ドリルダウン・未分類表示のテストを先行作成`
  2. `機能: useCategorySpending / useCategoryDrilldown フックを実装`
  3. `機能: 積み上げ棒グラフとカテゴリ表（ドリルダウン対応）を実装`
  4. `機能: categories ページに月選択とビューを統合`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 3.4 カテゴリ別支出ビューを実装。

## 成果物
- ui/lib/api/categories.ts
- ui/components/charts/CategoryStackedBar.tsx
- ui/components/tables/CategorySpendingTable.tsx
- ui/components/MonthSelector.tsx
- ui/src/app/categories/page.tsx
- 各 __tests__/

## 検証結果
- npm run test / typecheck / lint: 全件緑
- 親 / 子合計の一致確認

## 次のアクション提案
ui/Ph3/02 / 04 / 05 と並行可能、すべて完了で ui/Ph3/06 へ。
```

## 注意事項

- **金額は API から `Decimal` 文字列**で受領 → UI で `Intl.NumberFormat` 整形（`float` 経由しない）。
- **`null_category` キーの API レスポンス**: `api/Ph3/02` の仕様と整合。`category_id === null` の表記は `未分類`（i18n は Phase 4 以降）。
- **ドリルダウンのアクセシビリティ**: 行クリックは `<button>` または `role="button"` + キーボード（Enter/Space）対応。
- **積み上げの色割当**: 親カテゴリの色をベースに、子カテゴリは明度違いで派生（HSL ベース）。`recharts` の既定色は使わない。
