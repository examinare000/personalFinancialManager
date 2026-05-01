# postgres サービス 設計ドキュメント

## 配下ドキュメント
- `01-data-model.md` — データモデル詳細設計（テーブル / インデックス / 制約）
  - 関連 ADR: ADR-004, ADR-005, ADR-006

## 横断設計（root）
- `../../../docs/design/00-overview.md`
- `../../../docs/design/04-deployment-stack.md`
- `../../../docs/design/05-security-model.md`

## 関連サービス
- worker（取込・分類・整合性）: `../../../worker/docs/design/README.md`
