# personalFinancialManager (kakeibo)

個人向け資産・家計管理アプリケーション。NAS 上の Docker Compose で
セルフホストし、Tailscale 経由でのみ UI へアクセスする構成。

設計ドキュメントは `docs/plans/`、`docs/design/`、`docs/adr/` を参照。

## ローカル開発の起動手順

1. uv（Astral）と Docker をインストールしておく。Python 3.12 は uv が自動取得する。
2. シークレット雛形を複製し、安全な値に書き換える:
   ```bash
   cp secrets/pg_password.txt.example secrets/pg_password.txt
   chmod 600 secrets/pg_password.txt
   # 必要に応じて anthropic_key / paypal_api_secret / gmail_oauth_token も同様に複製
   cp .env.example .env
   ```
3. 依存をインストールする:
   ```bash
   make sync          # dev extras を含む
   ```
4. 開発用 Postgres を起動し、テストを実行する:
   ```bash
   docker compose up -d postgres
   make test
   ```
5. lint / format / typecheck をまとめて検証する:
   ```bash
   make check
   ```

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
| `ui` | ダッシュボード | nginx + 静的 HTML（Phase 3 で React に置換） |
| `caddy` | リバースプロキシ | 設定済み（profile: prod） |
| `backup` | 日次 pg_dump | sleep ループ常駐（profile: prod） |

## 主要ディレクトリ

| パス | 役割 |
|---|---|
| `src/kakeibo/` | コア実装（domain / adapters / ingest / worker / db / config） |
| `api/`, `worker/` | コンテナ build context（実体は `src/kakeibo/` を import） |
| `alembic/` | DB マイグレーション |
| `tests/` | pytest テスト（Phase 0 では `test_environment.py` のみ） |
| `docs/` | 設計書・ADR・開発プラン |
| `secrets/` | Docker secret 用ファイル雛形（実体は git 追跡対象外） |
| `inbox/`, `archive/`, `dead_letter/`, `backup/`, `data/` | 取込・保管ディレクトリ（実体は git 追跡対象外） |
