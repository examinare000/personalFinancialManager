"""バッチワーカーのプレースホルダ。

Phase 2.1 で watchdog Watcher、Phase 2.8 で cron 起動エントリポイントを
本パッケージに実装する。コア処理は ``kakeibo.ingest`` / ``kakeibo.worker``
配下を import して使う。
"""
