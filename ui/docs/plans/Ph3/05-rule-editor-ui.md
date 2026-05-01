---
title: ui/Ph3/05 ルール編集UI
service: ui
phase_task_id: 3.6
priority: 高
source_plan: docs/plans/01-development-plan.md
source_section: §4.3 Phase 3.6（行 367-377）
branch: feature/rule-editor-ui
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# ui/Ph3/05 ルール編集UI（Phase 3.6 主担当）

## このファイルの位置付け

原典 §4.3 Phase 3.6 を `ui` サービス担当の指示書として展開。`categorization_rules` の CRUD と **ドラッグ並び替え + dry-run プレビュー**を提供する UI。Phase3 完了条件 (c)「UI からルール CRUD」を直接満たす。

## 担当サービス

`compose.yml` `ui` サービス。`ui/src/app/rules/` にルール一覧と編集ページを追加。`api/Ph3/01` の Rule CRUD と `api/Ph3/03` の dry-run を呼び出す。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | `ui/Ph3/01`（雛形）+ `api/Ph3/01`（Rule CRUD）+ `api/Ph3/03`（dry-run） |
| 下流 | `ui/Ph3/06`（Playwright e2e） |

`ui/Ph3/02 / 03 / 04` と並列着手可能（独立ファイル）。

## 入力

1. **原典**: `docs/plans/01-development-plan.md` §4.3 Phase 3.6（行 367-377）
2. **分類設計**: `worker/docs/design/03-categorization-engine.md`
3. **ADR**: `docs/adr/008-three-tier-categorization.md`
4. **API 仕様**: `api/Ph3/01-flask-rest-api.md` の Rule CRUD、`api/Ph3/03-rule-dry-run-endpoint.md` の dry-run
5. **リスク**: `docs/plans/01-development-plan.md` §9 R-09（ReDoS）
6. **既存資産**: `ui/Ph3/01` の基盤

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `ui/package.json` | `@dnd-kit/core@^6`, `@dnd-kit/sortable@^8`, `react-hook-form@^7`, `@hookform/resolvers@^3` を追加 |
| `ui/lib/api/rules.ts` | `useRules()`, `useCreateRule()`, `useUpdateRule()`, `useDeleteRule()`, `useDryRunRule()`, `useReorderRules()` |
| `ui/components/rules/RuleForm.tsx` | フォーム（match_field / match_type / pattern / category_id） |
| `ui/components/rules/RulePreview.tsx` | dry-run 結果プレビュー（debounce 500ms） |
| `ui/components/rules/RuleList.tsx` | dnd-kit ソート可能リスト |
| `ui/components/rules/RuleDragHandle.tsx` | ドラッグハンドル（accessibility 対応） |
| `ui/components/rules/ApplyToExistingDialog.tsx` | 「既存取引に適用しますか？」モーダル |
| `ui/src/app/rules/page.tsx` | ルール一覧 |
| `ui/src/app/rules/[id]/page.tsx` | ルール編集 |
| `ui/src/app/rules/new/page.tsx` | ルール新規作成 |
| 各 `__tests__/` | フォームバリデーション・ドラッグ並び替え・dry-run プレビュー |

## 実装方針

### 1. ドラッグ並び替え: `@dnd-kit`

- `@dnd-kit/core` + `@dnd-kit/sortable` を採用
- `react-beautiful-dnd` は **メンテナンス停止状態のため不採用**
- キーボード操作対応（Tab → Space で持ち上げ → 矢印で移動 → Space で確定）

### 2. フォームバリデーション: `react-hook-form` + `zod`

- 各フィールドの `zod` スキーマで client / server 両側バリデーション
- `match_type='regex'` の場合、UI 側で **簡易構文チェック**（pattern 長 500 字以下）
- **ReDoS 検出は API 側の責務**（`api/Ph3/03` の `safe_regex` で SIGALRM タイムアウト）。UI は AbortController でフェイルセーフ。

### 3. dry-run プレビュー（debounce 500ms）

- フォーム入力時に debounce 500ms で `POST /api/rules/dry-run`
- レスポンスの `matched_count` と `sample` を `RulePreview` に表示
- API タイムアウト時は「プレビュー取得失敗（パターンを見直してください）」を表示

### 4. 保存後の既存取引への再分類

- 保存成功後 `ApplyToExistingDialog` を表示し、ユーザが Yes なら API（`api/Ph3/01` の Rule CRUD に `?apply_to_existing=true`）で再分類
- 原典 §4.3 Phase 3.6 受入基準には明示されていないが、ルール作成の運用上必須
- Phase 4.2 半自動学習との接合点（Phase 4 で本機能を拡張）

### 5. 優先度: 自動採番 + 手動編集

- 保存時に `priority` 値を自動採番（リスト順 × 10、例: 10, 20, 30）
- ドラッグ並び替え時は隣接値の中点を割り当て（10, 15, 20）、衝突したら全体再採番

### 6. Server / Client Component

- 一覧ページの初期データは Server Component で取得、ソート操作含むインタラクションは `"use client"`

## 依存パッケージ追加

`ui/package.json` runtime:
- `@dnd-kit/core@^6`
- `@dnd-kit/sortable@^8`
- `@dnd-kit/utilities@^3`
- `react-hook-form@^7`
- `@hookform/resolvers@^3`

## 実装手順（TDD）

### 1. Red

- `RuleForm.test.tsx`:
  - `test_validates_required_fields()`
  - `test_regex_pattern_too_long_shows_warning()`：500 文字超で警告表示
  - `test_invalid_match_type_shows_error()`
- `RulePreview.test.tsx`:
  - `test_dry_run_called_on_input_with_debounce()`：500ms debounce 検証
  - `test_shows_matched_count_and_sample()`
  - `test_handles_dry_run_timeout_error()`
- `RuleList.test.tsx`:
  - `test_drag_reorder_updates_priority()`
  - `test_keyboard_drag_reorder_works()`：Space + 矢印 で移動
  - `test_priority_collision_triggers_renumber()`
- `ApplyToExistingDialog.test.tsx`:
  - `test_yes_triggers_apply_to_existing_api_call()`
  - `test_no_skips_apply()`
- `page.test.tsx`:
  - `test_delete_rule_requires_confirmation()`
  - `test_delete_with_confirmation_calls_api()`

### 2. Green

1. `ui/package.json` に依存追加 → `npm install`
2. `ui/lib/api/rules.ts` で各フックを実装
3. `ui/components/rules/RuleForm.tsx` で `react-hook-form` + `zod` 実装
4. `ui/components/rules/RulePreview.tsx` で debounce + dry-run 呼出
5. `ui/components/rules/RuleList.tsx` で `@dnd-kit` ベースソート
6. `ui/components/rules/RuleDragHandle.tsx` でアクセシブルなハンドル
7. `ui/components/rules/ApplyToExistingDialog.tsx` で確認モーダル
8. `ui/src/app/rules/{page.tsx, [id]/page.tsx, new/page.tsx}` で統合

### 3. Refactor

- debounce ロジックを `ui/lib/hooks/useDebouncedValue.ts` に共通化
- dnd-kit のセンサー設定（`PointerSensor`, `KeyboardSensor`）を `ui/components/rules/_dnd.ts` に集約
- 優先度再採番ロジックを `ui/lib/rules/priority.ts` に純関数化（テスト容易性）

## 受入条件

原典 §4.3 Phase 3.6 受入基準：
- regex / contains / exact のいずれかを選択して保存可能
- ドラッグで優先度並び替え可能
- 既存取引へのプレビュー（このルールならN件マッチ）が表示
- バックエンドの dry-run エンドポイントを利用

加えて：
- **キーボード操作で並び替え可能**（accessibility）
- 優先度衝突時に自動再採番
- ReDoS 警告 / API タイムアウト時の UI フォールバック
- 削除操作に確認ダイアログ
- `tsc --strict` クリーン

## 品質ゲート

```bash
cd ui
npm run test -- rules
npm run typecheck
npm run lint
```

## ブランチ・コミット規約

- ブランチ: `feature/rule-editor-ui`
- コミット粒度（最低 7 件）：
  1. `テスト: ルール編集UI・dry-runプレビュー・並び替え・キーボード操作のテストを先行作成`
  2. `設定: dnd-kit と react-hook-form を導入`
  3. `機能: useRules / useDryRunRule / useReorderRules フックを実装`
  4. `機能: RuleForm（zodバリデーション + dry-runプレビュー）を実装`
  5. `機能: RuleList（dnd-kit並び替え + キーボード対応）を実装`
  6. `機能: rules ページとルール編集ページを統合`
  7. `機能: 既存取引への適用確認モーダルを実装`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 3.6 ルール編集UI を実装。

## 成果物
- ui/package.json（dnd-kit / react-hook-form 追加）
- ui/lib/api/rules.ts
- ui/components/rules/{RuleForm,RuleList,RulePreview,RuleDragHandle,ApplyToExistingDialog}.tsx
- ui/src/app/rules/{page.tsx, [id]/page.tsx, new/page.tsx}
- 各 __tests__/

## 検証結果
- npm run test / typecheck / lint: 全件緑
- キーボード並び替え動作確認
- ReDoS パターンでも UI がフリーズしない

## 次のアクション提案
ui/Ph3/02-04 完了後 ui/Ph3/06 (Playwright e2e) へ。
```

## 注意事項

- **`@dnd-kit` のキーボード操作**: `KeyboardSensor` を必ず登録。Tab → Space → 矢印 → Space のフローで accessible に。
- **dry-run の debounce**: 500ms は経験的閾値。短すぎると API 負荷、長すぎると UX 劣化。`useDebouncedValue` で集約。
- **API タイムアウト時の UI**: `fetch` の `AbortController` + 5 秒タイムアウト。`api/Ph3/03` のサーバ側 500ms タイムアウトより十分長く設定し、ネットワーク遅延を許容。
- **優先度の自動採番**: 中点割当が連続すると数値が縮退する（例: 10 → 15 → 12.5 → 11.25）ので、5 回程度の挿入で全体再採番（10, 20, 30, ...）するヘルパを `priority.ts` に実装。
- **削除時の確認ダイアログ**: 原典に明示なしだが、UX 上必須。Phase 4 でリストア機能（ソフトデリート）を入れる場合は ADR で再評価。
- **`@dnd-kit` の Server Component 互換**: dnd-kit は client only、ページ全体ではなく操作領域のみ `"use client"` でラップ。
