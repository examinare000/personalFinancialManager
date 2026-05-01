"""structlog ベースのログ設定。

agent-rules/12-security-guidelines.md §4 の要件に基づき、
出力前に機微キーをマスクする processor を提供する。
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

import structlog

# ログイベント辞書のキーが以下の文字列を含む場合、値を ``[REDACTED]`` に
# 置換する。部分一致のため ``api_token`` / ``anthropic_key`` 等も網羅される。
_SENSITIVE_KEYWORDS: tuple[str, ...] = (
    "password",
    "secret",
    "token",
    "key",
    "authorization",
)

_REDACTED = "[REDACTED]"


def _is_sensitive_key(key: str) -> bool:
    """ログキー名が機密キーワードを含むかを判定する。"""
    lower = key.lower()
    return any(keyword in lower for keyword in _SENSITIVE_KEYWORDS)


def redact_sensitive_processor(
    _logger: object,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """機微キーの値を ``[REDACTED]`` に置換する structlog processor。

    structlog の processor シグネチャ ``(logger, method_name, event_dict)``
    に従う。``event_dict`` は破壊的に書き換える契約のため、
    呼び出し側は同一辞書の再利用を想定しないこと。

    なお、ネストされた dict や list の中身は深掘りしない。
    深掘りが必要になったら再帰実装に切り替える（YAGNI 原則で当面は浅い検査のみ）。

    structlog 側の型は ``EventDict = MutableMapping[str, Any]`` のため、
    シグネチャを ``MutableMapping`` で受けて結合性を保つ。
    呼び出し側のテストでは通常の ``dict`` を渡すこともでき、
    ``dict`` は ``MutableMapping`` のサブタイプなので問題ない。
    """
    for key in list(event_dict.keys()):
        if _is_sensitive_key(key):
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging(*, debug: bool = False) -> None:
    """structlog のグローバル設定を行う。

    アプリケーション起動時に 1 回だけ呼ぶ想定。
    JSON 出力（本番）と人間可読出力（開発）を ``debug`` フラグで切り替える。
    """
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        redact_sensitive_processor,
    ]
    if debug:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(0),
        cache_logger_on_first_use=True,
    )


__all__ = ["configure_logging", "redact_sensitive_processor"]
