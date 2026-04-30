"""バッチワーカー層。

Phase 2.x で Gmail / PayPal / cron バッチ、Phase 4.x で LLM 分類・
Reconciler を実装する。Phase 0 では ``/tmp/worker_heartbeat`` を更新する
最小 idle ループのみを提供し、Docker HEALTHCHECK の判定基盤として機能する。

公開 API:
- ``run()``: heartbeat ループのエントリポイント。
"""

from __future__ import annotations

from .main import run

__all__ = ["run"]
