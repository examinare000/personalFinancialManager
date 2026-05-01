---
adr: 013
title: 設計・計画ドキュメントをサービス境界に同梱配置する
status: 採用済み
date: 2026-05-01
author: 池田遼介
related:
  - ADR-007
  - ADR-009
---

# ADR-013: 設計・計画ドキュメントをサービス境界に同梱配置する

## ステータス
採用済み

## 背景

Phase 0 までは、設計（`docs/plans/00-initial-design.md`）と詳細設計（`docs/design/01-data-model.md` 〜 `08-ingest-flow.md`）をリポジトリルートの `docs/` 配下に集約していた。Phase 1 着手にあたり以下の事実が顕在化した。

- ADR-009 で確定したサービス構成（postgres / worker / api / ui / caddy / backup）はすでに compose.yml と各 `<service>/Dockerfile` でコード境界として実体化されている
- 設計文書のほとんどはサービス専有である（`01-data-model` は postgres 専有、`02-ingest-adapters`・`03-categorization-engine`・`06-reconciler`・`07-output-integrations`・`08-ingest-flow` は worker 専有）
- Phase 1〜3 の実装プラン（`docs/plans/02〜09`、`12-13`）もサービスを跨がないタスクが大半で、サービス別に並列で進められる
- 一方、横断的に意味を持つ設計（`04-deployment-stack`・`05-security-model`）と俯瞰索引は全サービス共通の視点で読まれる

ルート `docs/design/` に全文書を平置きしたままだと、(a) 各サービスを単体で読み解こうとした際に関係ない文書まで視界に入る、(b) サービス担当者（人/エージェント）が Phase ごとの該当タスクを発見しにくい、(c) サービス境界とドキュメント境界が一致しないため新規機関追加・新規サービス追加の影響範囲が見積もりにくい、という摩擦があった。

## 検討した選択肢

### 選択肢A. ルート `docs/design/` 平置き継続（変更なし）
- メリット: 文書の所在が一意で迷わない。相互リンクが相対パス1段で済む
- デメリット: サービス境界とドキュメント境界が一致しない。Phase 1 の並列実装でサービス担当エージェントが無関係な文書を毎回スキャンすることになる

### 選択肢B. サービス専有 design は `<service>/docs/design/` に同梱、横断のみ root に残す（採用）
- メリット: コード境界（`<service>/`）と文書境界が一致する。各サービスの README から自分の design・関連 ADR・横断 design の3者へ最短で到達できる。新規サービス追加時に `<new-service>/docs/design/` を新設すれば構造が自己拡張する
- デメリット: 横断 design と専有 design の判定基準を運用上明文化する必要がある。サービスを跨ぐ参照の相対パスが長くなる（`../../../docs/design/...`）

### 選択肢C. 全 design を完全にサービス配下に分散（root `docs/design/` を廃止）
- メリット: 構造が完全に対称
- デメリット: `04-deployment-stack`・`05-security-model` は本質的に全サービス横断であり、特定サービス配下に置くと所有が曖昧になる。索引の置き場所も失う

## 決定

選択肢 B を採用する。

レポジトリ構造は以下のとおりとする。

```
docs/
├── adr/                       # 全 ADR（横断）
├── design/                    # 横断・俯瞰のみ
│   ├── 00-overview.md         # 全コンポーネント関係＋各サービス design への索引
│   ├── 04-deployment-stack.md # compose / network / Caddy / backup
│   ├── 05-security-model.md   # 脅威モデル・シークレット運用
│   └── README.md
└── plans/
    ├── 00-initial-design.md   # 設計書本体（履歴保全）
    ├── 01-development-plan.md # 全 Phase の実行計画（横断）
    ├── 02〜10-phase1-*.md     # Phase 1 タスク（横断的に保持）
    ├── 11〜13-phaseN-service-assignments.md # Phase 別サービス振り分け索引
    ├── postgres/PhN/...       # サービス × Phase のタスク指示書
    ├── worker/PhN/...
    ├── api/PhN/...
    └── ui/PhN/...

<service>/                     # postgres / worker / api / ui
└── docs/
    └── design/
        ├── README.md          # 当該サービスの design 索引
        └── NN-*.md            # 当該サービス専有の詳細設計
```

判定基準は以下とする。

- **横断 design（root 残留）**: 2 サービス以上の挙動・契約が同時に書かれる文書、もしくは全体俯瞰索引
- **専有 design（サービス配下）**: 1 サービスの内部実装で完結する文書（データモデル、アダプタ、分類エンジン等）
- **横断 plans（root 残留）**: Phase 全体の俯瞰、複数サービスの依存関係を含むタスク指示書
- **専有 plans（サービス配下）**: 1 サービス × 1 Phase に閉じたタスク指示書

## 理由

- ADR-009 で確定済みのコード境界（`<service>/Dockerfile` と compose.yml）にドキュメント境界を一致させることで、サービス単独でのメンテナンス・引継ぎ単位が自明になる
- Phase 1〜3 のタスク振り分け（`11-13-*-service-assignments.md`）はサービス別並列開発を前提としており、サービス担当が `<service>/docs/design/` と `docs/plans/<service>/PhN/` だけ追えば自分の責務を完結できる構造が必要だった
- 横断 design（deployment-stack / security-model）は本質的に「サービスを跨ぐ契約」を記述するため、特定サービスに所属させるとレビュー観点が偏る。root 残留が妥当
- ADR は意思決定の連続として番号で参照されるため、サービス分割の影響を受けない（root 一元管理を維持）
- 既存設計書本体（`plans/00-initial-design.md`）は履歴として不変に保ち、新規記述は専有 design 側に書き足す方針で乖離を防ぐ

## 結果

- 各サービス配下 README から、自サービスの専有 design・横断 design・関連 ADR の三方向に索引が張られる（実装済み: `postgres/docs/design/README.md`、`worker/docs/design/README.md`、`api/docs/design/README.md`、`ui/docs/design/README.md`）
- root `docs/design/00-overview.md` が全体俯瞰の唯一の入口として機能し、各サービス design への参照を集約する
- 実装プランは `docs/plans/<service>/PhN/` 配下にサービス×Phase の粒度で配置され、横断的な俯瞰は `10-phase1-overview.md` と `11〜13-*-service-assignments.md` が担う
- サービス専有 design 改訂は `<service>/docs/design/` 内で完結する。横断影響がある場合は ADR を新規発番してから root の横断 design を改訂する（ADR-007 のような既存 ADR のサービス所属は変更しない）
- 新規サービス追加時は `<new-service>/docs/design/README.md` と `docs/plans/<new-service>/PhN/` を新設し、`docs/design/00-overview.md` の索引を更新する手順を運用とする
- 文書探索コスト・サービス担当エージェントのコンテキスト読み込み量が減る一方、横断と専有の境界が将来曖昧になった場合は本 ADR を上書きする新 ADR を起票する
