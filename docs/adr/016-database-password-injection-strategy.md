---
adr: 016
title: PostgreSQL パスワードを SQLAlchemy URL.set でランタイム注入する
status: 採用済み
date: 2026-05-02
author: 池田遼介
related:
  - ADR-011
  - ADR-014
  - ADR-015
extends:
  - ADR-011
---

# ADR-016: PostgreSQL パスワードを SQLAlchemy URL.set でランタイム注入する

## ステータス
採用済み

## 背景

PR #14 で `compose.yml` の `DATABASE_URL` を以下の形式に統一した:

```
postgresql+psycopg://kakeibo@postgres:5432/kakeibo
```

パスワードを URL から完全に除外し、機密値は Docker secret（`/run/secrets/pg_password`）として `PG_PASSWORD_FILE` 経由で配信する設計に揃えた。これは ADR-011（認証情報非保持の発展形として、機密値はマウントされた secret ファイルからのみ供給する）に整合する。

しかしこの変更後、`alembic upgrade head` を実行すると以下で失敗する:

```
psycopg.OperationalError: connection failed: fe_sendauth: no password supplied
```

`DATABASE_URL` がパスワード抜きで宣言されているため、SQLAlchemy はそのまま psycopg3 ドライバへ渡し、psycopg3 が `password` パラメータ無しの接続要求を組み立て、PostgreSQL は `28P01` 相当を返す。`Settings.pg_password` は `_resolve_secret_file()` 経由で正しく `super-secret-pw` のような値を保持しているが、誰もそれを URL に合流させていなかった。

`shared/kakeibo_shared/db/session.py::create_db_engine` および `postgres/src/alembic/env.py::run_migrations_online` の双方で、`settings.pg_password` を URL に注入する経路が未実装である。本 ADR でその注入方式を定める。

## 検討した選択肢

### 選択肢A. compose.yml の `DATABASE_URL` に再びパスワードを埋め込む

`postgresql+psycopg://kakeibo:${PG_PASSWORD}@postgres:5432/kakeibo` のように、Docker Compose の変数展開で `PG_PASSWORD` 環境変数からパスワードを補間する。

- メリット:
  - URL を見れば接続情報が完結し、デバッグで「なぜ password 無しなのか」と迷わない
  - 実装変更が compose.yml のみで済む
- デメリット:
  - PR #14 の主旨（URL に機密を埋めない）を真っ向から覆す
  - `docker compose config` の出力に password が平文で出てしまい、`docker inspect` でも環境変数として露出する
  - `secrets:` 機構（メモリのみ展開、ログに出ない）を使う意義が希薄化する
  - `ANTHROPIC_API_KEY` 等の他 secret と取り扱いがチグハグになる

### 選択肢B. ドライバ依存の `connect_args` でパスワードを渡す

`create_engine(url, connect_args={"password": settings.pg_password})` で psycopg3 接続時に直接 password を注入する。

- メリット:
  - URL は触らずに接続層だけで完結
  - 実装シンプル
- デメリット:
  - `connect_args` のキーはドライバ固有（psycopg3 / psycopg2 / asyncpg で名前が異なる）。将来 driver を切り替えるたびに見直しが要る
  - `engine.url` 属性には password が含まれないため、SQLAlchemy 標準の `URL.__repr__` マスク（`***`）の二重防壁が機能しない（password は `connect_args` 辞書側にあり、辞書 repr は値を出してしまう）
  - alembic との橋渡しで重複実装になる（env.py 側でも同じ `connect_args` 構築が必要）

### 選択肢C. SQLAlchemy `URL.set(password=...)` でランタイムに URL を再構築（採用）

`make_url(settings.database_url).set(password=settings.pg_password)` で、ランタイムに password を合流させた `URL` オブジェクトを構築し、それを `create_engine` に渡す。`build_database_url(settings) -> URL` という小さなヘルパに切り出し、`create_db_engine` と alembic env.py の双方が経由する。

- メリット:
  - 機密は compose.yml に出さない（PR #14 の主旨を維持）
  - `URL.set` は SQLAlchemy 公式の immutable URL 操作 API で、ドライバ非依存
  - `URL.__repr__` が password を `***` にマスクするため、SQLAlchemy が出すあらゆる例外メッセージ・ログで自動マスクが効く（`Settings.__repr__` のマスクと併せて二重防壁）
  - alembic env.py から `Settings` を直接 import できるため、worker / api / alembic の 3 経路すべてで同じ URL 組み立てロジックを共有できる
- デメリット:
  - `Settings()` の二回インスタンス化（runtime と env.py 両方で行う）が発生するが、pydantic-settings の env-var パースは軽量で問題にならない
  - `URL` オブジェクトを返す関数を新設するため、既存の「URL は文字列」前提のコードを少しだけ更新する必要がある（`resolve_database_url()` は後方互換のため文字列返却で残置）

### 選択肢D. compose.yml の `environment` で `command` ラッパーを書き、起動前に secret を読んで `DATABASE_URL` を再エクスポート

`command: sh -c 'export DATABASE_URL="postgresql+psycopg://kakeibo:$(cat /run/secrets/pg_password)@postgres:5432/kakeibo"; exec ...'`

- メリット:
  - アプリ側コード変更ゼロ
- デメリット:
  - 各サービスのエントリポイントを書き換える必要があり、Dockerfile の `CMD` と二重管理になる
  - `ps -ef` でプロセスの ARGV を見ると展開後の URL が露出する
  - コマンドラインに password が入るため、コンテナ内のサイドカープロセスからも見える

## 決定

**選択肢 C を採用する。**

`shared/kakeibo_shared/db/session.py` に以下のヘルパを追加し、`create_db_engine` と alembic `env.py::run_migrations_online` の双方が経由する:

```python
def build_database_url(settings: Settings) -> URL:
    url = make_url(settings.database_url)
    if url.password is not None:
        return url                         # 開発 .env で URL に埋め込み済み → 尊重
    if settings.pg_password:
        return url.set(password=settings.pg_password)
    return url                             # fail-open: 28P01 で診断容易
```

優先順は以下の通り:

1. `DATABASE_URL` に既に password が含まれていればそれを使用
   （開発 `.env` の `kakeibo:devpassword@...` 運用を保全）
2. それ以外は `settings.pg_password` を `URL.set` で注入
3. どちらも無い場合は `password=None` のまま返す（fail-open）
   → 接続時に DB が `28P01` を返すため診断は容易

### オフラインモード（`alembic upgrade --sql`）の扱い

オフラインモードは SQL スクリプトを生成するだけで実 DB に接続しないため、Docker secret 経由のパスワード注入は不要。本 ADR では防御的設計として、オフラインモードでは `resolve_database_url()` の戻り値（password 抜きの URL 文字列）をそのまま使用し、`build_database_url` 経路（`URL` オブジェクト）は通さない。これにより、生成される SQL スクリプトの URL 表記に password が一切含まれないことを構造的に保証する。

## 理由

- **PR #14 の主旨を維持**: `DATABASE_URL` は引き続きパスワード抜きで宣言され、Docker secret が唯一のパスワード供給経路となる。`docker compose config` / `docker inspect` の出力にも機密が出ない
- **二重防壁による secret 漏洩防止**: `URL.__repr__` の `***` マスクが SQLAlchemy が送出するあらゆる例外メッセージ・ログで自動的に効く。`Settings.__repr__` のマスク（`[REDACTED]`）と併せて二重防壁となる。`connect_args` 案ではこの自動マスクが機能しない
- **後方互換性の保全**: 開発 `.env` で `DATABASE_URL=postgresql+psycopg://kakeibo:devpassword@localhost:5432/kakeibo` のようにパスワード埋め込み URL を使う運用は、優先順 1 により完全に保たれる
- **fail-open 設計の明示**: secret も URL も供給されない場合、隠蔽せず DB の `28P01` をそのまま見せることで、診断時の混乱を避ける（「secret ファイルが空だったのか、URL が壊れていたのか」が DB 側のエラーから明確になる）
- **3 経路の単一化**: worker / api / alembic がすべて同じ `build_database_url` を経由することで、URL 組み立てロジックの重複・乖離を構造的に防ぐ
- **ドライバ非依存**: `URL.set` は SQLAlchemy の標準 API のため、将来 psycopg3 → asyncpg 等への切替時にも変更不要

## 結果

### 実装変更

- `shared/kakeibo_shared/db/session.py`:
  - `build_database_url(settings: Settings) -> URL` を新設
  - `create_db_engine` を `build_database_url` 経由へ移行
  - `__all__` に `build_database_url` を追加
- `postgres/src/alembic/env.py`:
  - `run_migrations_online()` を `build_database_url` 経由へ移行
  - `resolve_database_url()` は文字列レベルの環境変数解決として残置（`run_migrations_offline()` 用 + 既存契約テスト `worker/tests/test_environment.py:119` の保全）
  - docstring に「実 engine 構築には `build_database_url` を使う」旨を追記

### テスト追加

`worker/tests/unit/test_db_url_injection.py` に 5 件の契約テスト:

1. `test_build_database_urlがpg_passwordをURLに注入する` — Docker secret 経由パスワードが `URL.password` に設定される
2. `test_build_database_urlはURL内のpasswordを優先する` — URL 内 password が `pg_password` より優先される（後方互換）
3. `test_build_database_urlはpg_password未設定時にURLをそのまま返す` — fail-open 動作
4. `test_build_database_url結果のreprがpasswordをマスクする` — `URL.__repr__` の `***` マスク動作の固定
5. `test_build_database_urlは空文字列passwordを意図的指定として尊重する` — `:@` 空文字列 password を意図的指定として尊重する契約の固定（`local trust` 構成への運用余地）

### 検証

- `docker compose run --rm worker pytest -q` → 159 passed（既存 154 + 新規 5）
- `docker compose run --rm worker alembic -c /app/postgres/src/alembic.ini upgrade head` → `fe_sendauth: no password supplied` エラー解消、`0001 → 0005` まで適用成功
- `docker compose logs` 内に `pg_password.txt` の secret 値が出現しないことを確認

### URL.__repr__ による password マスクの実機検証（二重防壁の根拠）

`SQLAlchemy URL` の各 string conversion 経路で password が `***` にマスクされることを確認した:

| 経路 | 結果 |
|---|---|
| `repr(url)` | `postgresql+psycopg://kakeibo:***@postgres:5432/kakeibo` |
| `str(url)` | `postgresql+psycopg://kakeibo:***@postgres:5432/kakeibo` |
| f-string `f"{url}"` | 同上 |
| `"{}".format(url)` | 同上 |
| `url.render_as_string()` | 同上 |
| `url.render_as_string(hide_password=False)` | 平文（明示時のみ） |

加えて、誤った password で `engine.connect()` を試行した際の `OperationalError` スタックトレースに password が露出しないことも実機確認済み。`alembic upgrade head --sql` の出力 SQL にも password の混入なし。

これにより、`Settings.__repr__` のキーワードベース `[REDACTED]` 化（`shared/kakeibo_shared/config.py:139-152`）と合わせて二重防壁が成立している。

### 運用への影響

- `compose.yml` の変更は不要（既に PR #14 でパスワード抜き URL に統一済み）
- 開発者が `.env` で password 埋め込み URL を使っていても引き続き動作する
- `secrets/pg_password.txt` を空にすると（あるいは `PG_PASSWORD_FILE` を未設定にすると）、起動時ではなく **DB 接続試行時** に `28P01` が出る。これは fail-open 設計による意図された挙動

## 今後の検討

- **`pg_password` の `SecretStr` 化**: 現在は `str | None` 型のため、`Settings.__repr__` のキーワードベースマスクに依存している。pydantic の `SecretStr` 型に切り替えれば、`__repr__` 自動マスクが型レベルで保証される。ただし `URL.set(password=...)` 呼出時に `.get_secret_value()` が必要となるため、影響範囲を確認した上で別 ADR で検討する
- **testcontainers 経路の `build_database_url` 統一**: 現状 `postgres/tests/unit/db/conftest.py::applied_database` は testcontainers の `get_connection_url()`（既に password 込み URL）を直接 `os.environ["DATABASE_URL"]` に流し込んでいる。本 ADR の優先順 1（URL 内 password 優先）により従来通り動作するが、運用経路と完全一致させるなら secret ファイルを mock する方式への切り替えも検討価値がある（テスト時間とのトレードオフ）
- **api コンテナ（Phase 2 以降）**: 現時点では api 配下に DB 接続コードはまだ無いが、追加時には必ず `create_db_engine(settings)` 経由とし、独自に `create_engine(settings.database_url, ...)` を呼ばないようコードレビューで担保する
- **本 ADR は ADR-011（認証情報非保持）の延長**: 「保持しない」原則の補完として「保持する場合は secret 経由のみ、URL 文字列には現れない」という追加制約をコードレベルで保証する位置づけ
- **Secret rotate 時の運用手順**: 本番 PostgreSQL パスワードをローテートする際、`compose.yml` の `DATABASE_URL` 環境変数に password が紛れ込んでいないことを再確認する手順を運用 README（または将来の `scripts/rotate_pg_password.sh`）に明記する。「URL 内 password が secret より優先される」設計（§決定 優先順 1）の副作用として、rotate 漏れの温床になる可能性があるため
