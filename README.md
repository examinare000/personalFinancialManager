# personalFinancialManager (kakeibo)

個人向け資産・家計管理アプリケーション。NAS 上の Docker Compose で
セルフホストし、Tailscale 経由でのみ UI へアクセスする構成。

設計ドキュメントは `docs/plans/`、`docs/design/`、`docs/adr/` を参照。

## ローカル開発の起動手順

ホストに必要なのは **Docker Engine** と **GNU Make** のみ。Python / uv / Node.js
はすべてコンテナ内に閉じ込める（ADR-009 / ADR-014 / ADR-015）。

1. Docker Engine と Make をインストールしておく。
2. シークレット雛形を複製し、安全な値に書き換える（4 種すべて必須。
   docs/design/05-security-model.md §5.1 準拠で `chmod 600` を強制する）:
   ```bash
   cp secrets/pg_password.txt.example secrets/pg_password.txt
   cp secrets/anthropic_key.txt.example secrets/anthropic_key.txt
   cp secrets/paypal_api_secret.txt.example secrets/paypal_api_secret.txt
   cp secrets/gmail_oauth_token.json.example secrets/gmail_oauth_token.json
   chmod 600 secrets/pg_password.txt secrets/anthropic_key.txt \
             secrets/paypal_api_secret.txt secrets/gmail_oauth_token.json
   cp .env.example .env
   ```
3. Python コンテナイメージをビルドする（依存は `shared/uv.lock` から `uv sync`
   される、ホスト uv 不要）:
   ```bash
   make build
   ```
4. テストを実行する（worker コンテナで pytest を起動）:
   ```bash
   make test
   ```
5. lint / format / typecheck をまとめて検証する（すべて worker コンテナ内）:
   ```bash
   make check
   ```

依存を変更したい場合は `shared/pyproject.toml` を編集してから:

```bash
make lock      # shared/uv.lock を再生成（uv 公式 image 経由）
make build     # 新しい lock で再ビルド
```

## DB 初期化（alembic）

Phase 1.1 以降のマイグレーション本体投入後、開発・本番ともに以下の手順で
スキーマを最新化する。Phase 0 時点ではマイグレーションファイル本体は
未作成のため、コマンドは「No-op で 0 件適用」を確認するための疎通検証に位置づく。

```bash
# 1) postgres コンテナを起動して healthy になるまで待つ
docker compose up -d postgres

# 2) worker コンテナで alembic upgrade head を実行する（postgres/src/alembic を mount）
docker compose run --rm worker alembic -c /app/postgres/src/alembic.ini upgrade head
```

ホスト側に Python を導入していないため、開発ホストから直接 `alembic` を
叩くことはしない（ADR-015）。必ず worker コンテナ経由で実行する。

## Docker Compose スタックの起動

Phase 0 では api / ui / worker / postgres / caddy / backup の 6 コンテナを
別々に立てて連携させる構成になっている。すべて最小スタブのため
`docker compose up -d` で healthy 状態まで到達することを確認できる。

```bash
# シークレット雛形を実体化（初回のみ）
cp secrets/pg_password.txt.example secrets/pg_password.txt
cp secrets/anthropic_key.txt.example secrets/anthropic_key.txt
cp secrets/paypal_api_secret.txt.example secrets/paypal_api_secret.txt
cp secrets/gmail_oauth_token.json.example secrets/gmail_oauth_token.json

# ビルド & 起動
docker compose build
docker compose --profile worker --profile prod up -d
# （開発時に worker / caddy / backup を含めず最小起動するなら）
docker compose up -d postgres api ui

# 起動確認
docker compose ps                      # 各コンテナが (healthy) になることを確認
curl http://127.0.0.1:8000/health      # {"status": "ok"}
curl http://127.0.0.1:3000/            # ダッシュボードのスタブ HTML

# 片付け
docker compose down
```

各コンテナの役割と Phase 0 時点の実装状況:

| コンテナ | 役割 | Phase 0 実装 |
|---|---|---|
| `postgres` | DB（PostgreSQL 16） | 本番同等 |
| `api` | Flask REST API | `/health` のみ（Phase 3.1 で本実装） |
| `worker` | バッチワーカー | heartbeat ループのみ（Phase 2.x で本実装） |
| `ui` | ダッシュボード | Next.js 14+（App Router / standalone build, Phase 3 でロジックを実装） |
| `caddy` | リバースプロキシ | 設定済み（profile: prod） |
| `backup` | 日次 pg_dump | sleep ループ常駐（profile: prod） |

## 主要ディレクトリ

| パス | 役割 |
|---|---|
| `shared/pyproject.toml` | Python 依存マニフェスト（ADR-015、`[tool.uv].package = false`） |
| `shared/uv.lock` | universal lockfile（コンテナ内で生成、ホスト uv 不要） |
| `shared/kakeibo_shared/` | サービス横断の共有 Python モジュール（config / logging / db / domain）。PYTHONPATH 経由で配信 |
| `api/src/kakeibo_api/` | Flask API サービス専有コード |
| `api/tests/` | api サービスの振る舞いテスト |
| `api/Dockerfile` | api コンテナのビルド定義 |
| `worker/src/kakeibo_worker/` | バッチ worker サービス専有コード（ingest / adapters 等） |
| `worker/tests/` | worker / kakeibo_shared / alembic のテスト（worker は dev/test 基盤も兼ねる） |
| `worker/Dockerfile` | worker コンテナのビルド定義 |
| `postgres/src/alembic/` | DB マイグレーション（postgres サービス所有、worker からマウント実行） |
| `postgres/src/sql/queries/` | 共通 SQL クエリ（postgres サービス所有） |
| `postgres/src/alembic.ini` | alembic 設定 |
| `postgres/docs/plans/`, `worker/docs/plans/` ほか | サービス専有の Phase 別タスク指示書 |
| `ui/` | Next.js ダッシュボード（Phase 3 以降で UI 本実装） |
| `caddy/` | リバースプロキシ設定・Caddy 永続ボリューム |
| `tests/` | リポジトリ横断の構造テスト（compose / docs / 構造、Python パッケージ非依存） |
| `docs/` | 横断設計書・ADR・横断プラン |
| `secrets/` | Docker secret 用ファイル雛形（実体は git 追跡対象外） |
| `inbox/`, `archive/`, `dead_letter/`, `backup/`, `data/` | 取込・保管ディレクトリ（実体は git 追跡対象外） |
