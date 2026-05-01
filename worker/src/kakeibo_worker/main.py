"""worker の最小 idle ループ実装。

設計指針:
- Phase 0 では実バッチ処理は行わず、``heartbeat_path`` を定期更新するだけの
  常駐プロセスとする。Docker の HEALTHCHECK が mtime を見て生存判定する。
- SIGTERM / SIGINT を受けたら graceful に停止する。テストでは ``stop_event``
  を直接立てて停止できるよう、シグナルハンドラとイベントフラグを併用する。
- structlog でログ出力。設定は ``kakeibo.logging.configure_logging`` に委譲。

Phase 2.x で本実装に置き換える際、本ファイルは取込スケジューラの
ディスパッチャに発展する想定（``run`` の中で複数のジョブを並列起動）。
"""

from __future__ import annotations

import os
import signal
import threading
import time
from pathlib import Path
from types import FrameType

import structlog

from kakeibo_shared.logging import configure_logging

_DEFAULT_HEARTBEAT_PATH = Path("/tmp/worker_heartbeat")
_DEFAULT_INTERVAL_SECONDS = 60.0


def _resolve_heartbeat_path(heartbeat_path: Path | None) -> Path:
    """heartbeat ファイルパスを解決する。

    優先度: 引数 > 環境変数 ``WORKER_HEARTBEAT_PATH`` > 既定 ``/tmp/worker_heartbeat``。
    """
    if heartbeat_path is not None:
        return heartbeat_path
    env_value = os.environ.get("WORKER_HEARTBEAT_PATH")
    if env_value:
        return Path(env_value)
    return _DEFAULT_HEARTBEAT_PATH


def _touch_heartbeat(path: Path) -> None:
    """heartbeat ファイルを touch する（mtime 更新）。

    親ディレクトリが無い場合は作成する。失敗時は呼び出し側で握りつぶさず
    例外を伝播させる（HEALTHCHECK で異常検知させるのが目的）。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # ファイルが存在しなければ作成、存在すれば mtime を現在時刻に更新する。
    path.touch(exist_ok=True)
    # 明示的に utime を打って「mtime が確実に進む」ことを保証する。
    # 環境によっては touch だけでは秒単位の解像度で停滞することがあるため。
    now = time.time()
    os.utime(path, (now, now))


def _install_signal_handlers(stop_event: threading.Event) -> None:
    """SIGTERM / SIGINT をフックして stop_event を立てる。

    threading.Event を介して間接的にループを停止させることで、
    シグナルハンドラ内で重い処理を行わない（async-signal-safe を維持）。

    pytest の thread からは signal.signal が呼べないため、
    メインスレッド以外では ``ValueError`` が出る。その場合はスキップする。
    """

    def _handler(_signum: int, _frame: FrameType | None) -> None:
        stop_event.set()

    try:
        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)
    except ValueError:
        # サブスレッドから呼ばれた場合は ``ValueError: signal only works
        # in main thread`` が出る。テスト経路では stop_event を直接渡すため
        # ハンドラ未登録でも問題ない。
        pass


def run(
    *,
    heartbeat_path: Path | None = None,
    interval_seconds: float | None = None,
    stop_event: threading.Event | None = None,
) -> None:
    """worker の常駐ループ本体。

    Args:
        heartbeat_path: heartbeat ファイルのパス。``None`` なら環境変数
            ``WORKER_HEARTBEAT_PATH`` または既定値を使う。
        interval_seconds: heartbeat 更新間隔（秒）。``None`` なら 60 秒。
        stop_event: 外部停止シグナル。``None`` なら新規生成し、
            SIGTERM/SIGINT ハンドラに紐付ける。

    Returns:
        正常終了時は何も返さない。例外は呼び出し側に伝播する。

    本関数は次の不変条件を保つ:
    - 起動直後（最初の sleep 前）に最低 1 回 heartbeat を更新する
    - stop_event が立つまで interval ごとに heartbeat を更新し続ける
    - stop_event が立ったら次の sleep を待たず即座に終了する
    """
    configure_logging(debug=os.environ.get("LOG_LEVEL", "").upper() == "DEBUG")
    log = structlog.get_logger(__name__)

    resolved_path = _resolve_heartbeat_path(heartbeat_path)
    interval = interval_seconds if interval_seconds is not None else _DEFAULT_INTERVAL_SECONDS

    if stop_event is None:
        stop_event = threading.Event()
        _install_signal_handlers(stop_event)

    log.info(
        "worker_started",
        heartbeat_path=str(resolved_path),
        interval_seconds=interval,
    )

    # 起動直後に必ず 1 回 heartbeat を打つ。これにより HEALTHCHECK が
    # 起動直後（healthcheck の interval 前）に false negative を出さない。
    _touch_heartbeat(resolved_path)

    while not stop_event.is_set():
        # stop_event.wait(timeout) は graceful shutdown の信号を即座に
        # 受け取りつつ、interval 秒のスリープも実現する。time.sleep より
        # キャンセル応答性が良い。
        if stop_event.wait(timeout=interval):
            break
        _touch_heartbeat(resolved_path)

    log.info("worker_stopped", heartbeat_path=str(resolved_path))


__all__ = ["run"]
