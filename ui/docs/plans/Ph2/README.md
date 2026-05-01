---
title: ui サービス Phase2 タスク指示書
service: ui
phase: 2
status: NoTasks
parent_index: docs/plans/12-phase2-service-assignments.md
last_updated: 2026-05-01
---

# ui サービス Phase2 タスク指示書

## 結論：Phase2 では本サービス向けの新規実装タスクなし

`compose.yml` `ui` サービス（Next.js 雛形）は Phase 0 で配備済み。Phase 1 と同様、Phase 2 でも **本格着手しない**。

`docs/plans/01-development-plan.md` §4.2 のタスク 2.1〜2.8 はバックエンド自動取込のみで、UI で操作する画面や設定変更フローは含まれない。

## サービス境界（参考）

| 範囲 | Phase 2 での扱い |
|---|---|
| Next.js アプリ（`ui/app/`） | 変更なし |
| Dockerfile / `package.json` | 変更なし |
| `tests/unit/test_ui_nextjs.py` | 既存挙動を維持 |

## Phase2 の間に ui サービスへ波及する変更（許容例）

| 変更例 | 受入可否 | 備考 |
|---|---|---|
| UI 雛形に手を入れる | 不要 | Phase 2 では一切変更しない |
| `ui/Dockerfile` の改修 | 不要 | – |

`agent-rules/00-core-principles.md` 3原則 §1 デグレッション防止に従い、UI 側の既存テスト（`tests/unit/test_ui_nextjs.py`）を壊さないこと。

## Phase 3.2 への申し送り

Phase 3 で本サービスに本格着手するときの起点：

- 原典: `docs/plans/01-development-plan.md` §4.3 Phase 3.2 React Dashboard 雛形
- ブランチ: `feature/react-dashboard-scaffold`
- Phase 2 完了時点で `worker` 側に取引データが日次で蓄積される状態になっているので、Phase 3.3 月次推移グラフが意味のあるデータを描画できる前提が整う

Phase 3.2 着手時に `ui/docs/plans/Ph3/01-react-dashboard-scaffold.md` を新設する。

## 担当 Worker サブエージェント

Phase2 期間中は原則不要。

| Worker | 役割 |
|---|---|
| Reviewer | `tests/unit/test_ui_nextjs.py` が共通設定変更（`pyproject.toml` 等）で破壊されていないか Read のみで確認 |
