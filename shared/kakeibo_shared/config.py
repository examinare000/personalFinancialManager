"""アプリケーション設定（pydantic-settings）。

設計指針:
- 通常の設定は環境変数で受け取る
- シークレット類は Docker secret 規約 ``<NAME>_FILE`` でファイルパスを
  環境変数として受け取り、ファイル本体を読んで値とする
  （docs/design/05-security-model.md §5）
- ``__repr__`` で機微属性をマスクし、誤ってログ・例外に値を露出させない
  （agent-rules/12-security-guidelines.md §4）
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ログ・``__repr__`` で値を伏せる属性名のサフィックス／キーワード。
# 部分一致で判定する（例: ``api_token`` は ``token`` を含むのでマスク対象）。
_SENSITIVE_KEYWORDS: tuple[str, ...] = (
    "password",
    "secret",
    "token",
    "key",
    "authorization",
)


def _resolve_secret_file(value: str | Path | None) -> str | None:
    """``*_FILE`` 環境変数で指定されたファイルから secret 値を読む。

    末尾の改行・空白を ``rstrip`` で除去し、Docker secret の運用慣習に合わせる。
    値が None または空のときは None を返し、後続のバリデーションに委ねる。
    """
    if value is None:
        return None
    path = Path(str(value))
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").rstrip()


def _is_sensitive_field(name: str) -> bool:
    """フィールド名に機密キーワードが含まれるかを判定する。"""
    lower = name.lower()
    return any(keyword in lower for keyword in _SENSITIVE_KEYWORDS)


class Settings(BaseSettings):
    """アプリケーション全体の設定。

    pydantic-settings は環境変数を大文字小文字無視で読み取るため、
    ``DATABASE_URL`` は ``database_url`` フィールドにマップされる。

    Docker secret 規約:
    - ``PG_PASSWORD_FILE`` → ``pg_password``
    - ``ANTHROPIC_API_KEY_FILE`` → ``anthropic_api_key``
    - ``PAYPAL_API_SECRET_FILE`` → ``paypal_api_secret``

    （Gmail OAuth トークンは JSON 構造のためファイルパスのまま保持し、
    呼び出し側でパースする。）
    """

    model_config = SettingsConfigDict(
        env_file=None,  # .env は本番でも開発でも自動読込しない（明示的に渡す）
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 一般設定 ──
    database_url: str = Field(
        ...,
        description="SQLAlchemy 用の Postgres 接続文字列",
    )
    inbox_path: Path = Field(
        default=Path("/inbox"),
        description="取込待ちファイルの監視ディレクトリ",
    )
    archive_path: Path = Field(
        default=Path("/archive"),
        description="取込済み原本の保管先",
    )
    dead_letter_path: Path = Field(
        default=Path("/dead_letter"),
        description="パース失敗ファイルの隔離先",
    )

    # ── シークレット系（FILE 規約） ──
    # 値を直接環境変数で受けることも許容するが、Production では FILE 経由が原則。
    pg_password: str | None = Field(default=None)
    anthropic_api_key: str | None = Field(default=None)
    paypal_api_secret: str | None = Field(default=None)
    gmail_oauth_token_path: Path | None = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def _load_secret_files(cls, values: Any) -> Any:
        """``*_FILE`` 環境変数で指定されたファイルから secret を解決する。

        pydantic-settings は ``*_FILE`` 環境変数を Settings のフィールドに
        マップしないため（Settings には ``pg_password_file`` 等のフィールドを
        定義していない）、ここでは環境変数を直接参照して FILE 系のキーから
        対応する値フィールドへ secret を展開する。
        """
        if not isinstance(values, dict):
            return values

        # pydantic から渡される入力 dict のキー・値型は実行時には不定だが、
        # 本ロジックの責務上は ``str -> 任意`` として扱える。pyright の
        # strict モードで「partially unknown」警告が出るため、明示的に
        # ``dict[str, Any]`` にキャストして以降の get/set を型付ける。
        typed_values: dict[str, Any] = cast("dict[str, Any]", values)

        # 既に値が dict で渡されている場合と、環境変数から拾う場合の両方に対応。
        # 環境変数は OS 側で大文字に正規化されているため、そのまま大文字キーで読む。
        env_mapping = {
            "PG_PASSWORD_FILE": "pg_password",
            "ANTHROPIC_API_KEY_FILE": "anthropic_api_key",
            "PAYPAL_API_SECRET_FILE": "paypal_api_secret",
        }
        for env_key, value_key in env_mapping.items():
            file_path = os.environ.get(env_key)
            if file_path and typed_values.get(value_key) in (None, ""):
                resolved = _resolve_secret_file(file_path)
                if resolved is not None:
                    typed_values[value_key] = resolved

        # Gmail のみ JSON ファイルパスのまま保持する（呼び出し側でパース）。
        gmail_file = os.environ.get("GMAIL_OAUTH_TOKEN_FILE")
        if gmail_file and typed_values.get("gmail_oauth_token_path") in (None, ""):
            typed_values["gmail_oauth_token_path"] = gmail_file

        return typed_values

    def __repr__(self) -> str:
        """機微属性をマスクした再現可能表現を返す。

        誤ってロガーやスタックトレースに値が露出することを防ぐ。
        """
        parts: list[str] = []
        for name, value in self.__dict__.items():
            if value is None:
                parts.append(f"{name}=None")
            elif _is_sensitive_field(name):
                parts.append(f"{name}='[REDACTED]'")
            else:
                parts.append(f"{name}={value!r}")
        return f"{self.__class__.__name__}({', '.join(parts)})"
