"""``python -m kakeibo.worker`` で worker 常駐プロセスを起動する。

Docker コンテナの ``CMD`` から呼ばれることを想定している。
"""

from __future__ import annotations

from kakeibo.worker import run


def main() -> None:
    """``run()`` を既定パラメータで起動する。"""
    run()


if __name__ == "__main__":
    main()
