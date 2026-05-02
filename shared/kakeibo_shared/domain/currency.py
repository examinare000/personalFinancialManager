"""通貨コードバリデータ（ISO 4217 風 3 文字英大文字）。

設計準拠:
- ``postgres/docs/plans/Ph1/03-domain-types.md`` §実装方針3, §対象ファイル, §TDD Refactor
- ``Transaction.currency`` と ``BalanceSnapshot.currency`` の重複バリデーションを単一関数に集約する
  （DRY / 解決責務の一元化）。
"""

from __future__ import annotations


def validate_currency_code(code: str) -> None:
    """ISO 4217 風 3 文字英大文字を満たさない通貨コードを早期に弾く。

    plan §実装方針3 の規定:
    - ``len == 3``、``isalpha``、``isupper`` のすべてを満たすこと。
    - ``str`` 以外で渡された場合は ``len()`` で曖昧なエラーを出す前に ``TypeError``
      を発生させる（Fail Fast）。

    Raises:
        TypeError: ``code`` が ``str`` でない（呼び出し側の型契約違反）。
        ValueError: 3 文字英大文字を満たさない（``"JP"`` / ``"jpy"`` / ``"JPYY"`` 等）。
    """
    # 静的型は ``str`` だが、ISO 4217 数字コード（``int 392`` 等）が誤って
    # 渡されるケースを実行時に弾く（Fail Fast）。pyright strict は型注釈通りの値
    # しか流入しないと解釈してしまうため明示的に抑止する。
    if not isinstance(code, str):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"currency code must be str, got {type(code).__name__}")
    if len(code) != 3 or not code.isalpha() or not code.isupper():
        raise ValueError(f"invalid currency code: {code!r}")
