# worker サービス 設計ドキュメント

## 配下ドキュメント
- `02-ingest-adapters.md` — 取込アダプタ詳細設計（CSV/メール/API）
  - 関連 ADR: ADR-001, ADR-007
- `03-categorization-engine.md` — カテゴリ分類エンジン詳細設計
  - 関連 ADR: ADR-008
- `06-reconciler.md` — 連動取引・残高整合性 詳細設計
  - 関連 ADR: ADR-006
- `07-output-integrations.md` — 外部出力連携 詳細設計
- `08-ingest-flow.md` — 取込フロー詳細設計
  - 関連 ADR: ADR-001, ADR-007

## 横断設計（root）
- `../../../docs/design/00-overview.md`
- `../../../docs/design/04-deployment-stack.md`
- `../../../docs/design/05-security-model.md`

## 関連サービス
- postgres（データモデル）: `../../../postgres/docs/design/README.md`
