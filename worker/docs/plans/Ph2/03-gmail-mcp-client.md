---
title: worker/Ph2/03 Gmail MCP 接続
service: worker
phase_task_id: 2.3
priority: 高
source_plan: docs/plans/01-development-plan.md
source_section: §4.2 Phase 2.3（行 235-245）
branch: feature/gmail-mcp-client
base_branch: develop
status: Ready
last_updated: 2026-05-01
---

# worker/Ph2/03 Gmail MCP 接続（Phase 2.3）

## このファイルの位置付け

原典 `docs/plans/01-development-plan.md` §4.2 Phase 2.3 を `worker` サービス担当の指示書として展開。Phase2 の EC メールパーサ群（2.4 / 2.5 / 2.6）の **共通取得基盤**を作る。

## 担当サービス

`worker` コンテナ。Gmail API を **`gmail.readonly` スコープに限定** で叩き、対象ラベル/送信元のメール一覧と本文を取得して `RawMail` 共通型に正規化する。OAuth リフレッシュトークンは Docker secret 経由で読み込む（ADR-011 認証情報非保持）。

## 上流・下流

| 区分 | タスク |
|---|---|
| 上流 | なし（`worker/Ph2/01` Watcher と並行可） |
| 下流 | `worker/Ph2/04`（Amazon）, `05`（楽天）, `06`（Yahoo） |

## 入力

1. **原典**: §4.2 Phase 2.3（行 235-245）
2. **セキュリティ**: `docs/design/05-security-model.md`
3. **アダプタ設計**: `worker/docs/design/02-ingest-adapters.md`
4. **ADR**: `docs/adr/011-no-credentials-storage.md`
5. **既存資産**:
   - `compose.yml` `worker` の secret `gmail_oauth_token` と環境変数 `GMAIL_OAUTH_TOKEN_FILE=/run/secrets/gmail_oauth_token`
   - `secrets/gmail_oauth_token.json.example`（フォーマット参考）
   - `shared/kakeibo_shared/config.py` `gmail_oauth_token_path: Path | None`（既存）
6. **依存追加が必要**: `pyproject.toml` に `google-auth>=2.30,<3` および `google-api-python-client>=2.130,<3` を `[project.optional-dependencies].mail` に追加（`mail-parser` 系と同じ extras に集約）

## 期待される出力ファイル

| パス | 役割 |
|---|---|
| `pyproject.toml` | `mail` extras に `google-auth`, `google-api-python-client` 追加 |
| `shared/kakeibo_shared/domain/raw_mail.py` | `RawMail` dataclass（`message_id: str`, `from_addr: str`, `subject: str`, `received_at: datetime`, `body_text: str`, `body_html: str | None`, `labels: tuple[str, ...]`） |
| `shared/kakeibo_shared/domain/__init__.py` | `RawMail` 公開 API 追加 |
| `worker/src/kakeibo_worker/adapters/gmail/__init__.py` | パッケージ初期化 |
| `worker/src/kakeibo_worker/adapters/gmail/client.py` | OAuth トークン読込 + Gmail API 呼出 |
| `worker/src/kakeibo_worker/adapters/gmail/auth.py` | リフレッシュトークン → アクセストークン変換、ログマスキング |
| `tests/unit/adapters/gmail/test_client.py` | API レスポンスをモックして `RawMail` 正規化検証 |
| `tests/unit/adapters/gmail/test_auth.py` | トークンマスキング検証（ログキャプチャ） |
| `tests/fixtures/gmail/sample_message.json` | Gmail API `users.messages.get` レスポンスの fixture |

## 実装方針

1. **OAuth スコープ**: 読み取り専用 `https://www.googleapis.com/auth/gmail.readonly` のみ。`scopes` を **コードで定数化** し、ハードコード以外を許可しない。
2. **トークン読込**: `Settings.gmail_oauth_token_path` から JSON を読み、`google.oauth2.credentials.Credentials.from_authorized_user_info(...)` でロード。失効時は `refresh()` を試行し、失敗時は `RuntimeError("Gmail OAuth token expired")` を送出（自動再認可は Phase 2 では行わない）。
3. **取得対象**: `query` パラメータで `from:auto-confirm@amazon.co.jp newer_than:30d` のような検索式を渡す API。Amazon / 楽天 / Yahoo のクエリは各パーサ（2.4 / 2.5 / 2.6）が指定する。
4. **`RawMail` 正規化**: メッセージID / 送信元 / 件名 / 受信日時 / 本文（plain + html） / ラベル を抽出。base64url デコードは `email.message_from_bytes` で実施。
5. **ログマスキング**: `auth.py` 内で `repr(credentials)` のような呼び出しを避け、トークン値が `structlog` ログに乗らないよう **専用ログ helper** を経由（`log.info("gmail_token_loaded", path=str(token_path))` のように値ではなくパスのみ記録）。
6. **MCP 接続の有無**: 原典タイトルは「Gmail MCP 接続」だが、本タスクは **Google API クライアントによる直接接続** で実装。MCP 経由のラッパは Phase 4 以降で検討（実機関 API のクライアントは可逆実装を優先）。タイトルとの差異はコメントに記載。

## 実装手順（TDD）

### 1. Red

- `tests/fixtures/gmail/sample_message.json` を Gmail API `users.messages.get` のサンプル形式で作成（合成。実メールデータは入れない）。
- `tests/unit/adapters/gmail/test_client.py`：
  - `client.list_messages(query="...")` がメッセージ ID リストを返す（HTTP モック）
  - `client.get_message(msg_id)` が `RawMail` を返す
  - スコープ違反のクライアントを inject すると `ValueError`
- `tests/unit/adapters/gmail/test_auth.py`：
  - リフレッシュトークン JSON 読込でトークン値が `caplog` に含まれない
  - 期限切れトークンで `RuntimeError`
- `tests/unit/domain/test_raw_mail.py` で `RawMail` バリデーション。

### 2. Green

- `shared/kakeibo_shared/domain/raw_mail.py` で dataclass + バリデーション。
- `worker/src/kakeibo_worker/adapters/gmail/auth.py` で OAuth ロード（`google.oauth2.credentials.Credentials`）。
- `worker/src/kakeibo_worker/adapters/gmail/client.py` で `googleapiclient.discovery.build("gmail", "v1", credentials=...)` をラップ。
- 各テストを順に通す。

### 3. Refactor

- スコープ定数を `_SCOPES = ("https://www.googleapis.com/auth/gmail.readonly",)` でモジュールトップレベル化。
- `RawMail` 生成ロジックを `_message_to_raw_mail(msg: dict) -> RawMail` に抽出。

## 受入条件

- OAuth スコープが `gmail.readonly` のみであることをコードレベル + テストで保証
- リフレッシュトークンが Docker secret 経由（`Settings.gmail_oauth_token_path`）で読み込まれる
- 平文ログにトークンが出力されない（`caplog` で検証）
- 取得結果が `RawMail` に正規化される
- スコープ違反検出時に `ValueError`
- `pyright` クリーン、`ruff` 違反ゼロ

## 品質ゲート

```bash
pytest tests/unit/adapters/gmail/ tests/unit/domain/test_raw_mail.py
ruff check .
pyright
```

## ブランチ・コミット規約

- ブランチ: `feature/gmail-mcp-client`
- コミット粒度（最低 5 件）：
  1. `テスト: RawMail型 / Gmail OAuth / メッセージ取得 / トークンマスキングのテストを先行作成`
  2. `設定: google-auth と google-api-python-client を mail extras に追加`
  3. `機能: RawMail共通型を追加`
  4. `機能: gmail.readonly限定のOAuthクライアントを実装（トークンマスキング含む）`
  5. `機能: Gmail APIクライアントとメッセージ→RawMail正規化を実装`

## 完了報告テンプレ

```markdown
## 実施内容
Phase 2.3 Gmail 読み取り専用クライアントを実装。

## 成果物
- shared/kakeibo_shared/domain/raw_mail.py
- worker/src/kakeibo_worker/adapters/gmail/{client,auth}.py
- tests/unit/{domain/test_raw_mail.py, adapters/gmail/}
- tests/fixtures/gmail/sample_message.json
- pyproject.toml（mail extras 拡張）

## 検証結果
- 全件緑
- スコープが gmail.readonly に限定されることを確認
- caplog でトークン非露出を確認
- pyright / ruff: クリーン

## 次のアクション提案
worker/Ph2/04 (Amazon) / 05 (楽天) / 06 (Yahoo) を 3 並列で着手可能。
```

## 注意事項

- **スコープ拡張禁止**: 将来「メールを送信したい」「ラベル変更したい」というニーズが出ても、本タスクのスコープ（readonly 限定）は変更不可。必要なら ADR を新規発番すること（`docs/adr/011-no-credentials-storage.md` の精神に沿う）。
- **トークン値のログ出力厳禁**: `repr(credentials)`, `vars(credentials)`, `__dict__` 経由でログに乗せないこと。マスキング helper を必ず通す。
- **実メールデータを fixture に入れない**: 件名・本文は合成。実 EC 注文の番号・金額・氏名は絶対に含めない。
- **MCP の意味**: 原典タイトルが「Gmail MCP」だが、Phase 2 では Anthropic の Model Context Protocol ではなく Google API 直接接続を採用する（より単純で監査しやすい）。MCP 化は Phase 4 以降で再評価。指示書本文の `client.py` 名はこの方針を反映。
- リフレッシュトークン失効時のリトライは Phase 2 では未実装。`R-04`（リスク）として残置し、運用 90 日でレビューする。
