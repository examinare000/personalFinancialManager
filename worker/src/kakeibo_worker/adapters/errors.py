"""取込アダプタ層が送出する例外型。

Phase 1.3 の ``IngestAdapter`` ABC を実装する機関別アダプタが、入力バイト列の
不整合（エンコーディング・列構造・行データ）を検出した際に送出する例外を集約する。
``AdapterError`` 派生に揃えることで、Phase 1.6 取込 CLI から
``except AdapterError`` での一括ハンドリングを可能にする。

設計準拠:
- ``worker/docs/plans/Ph1/04-ingest-adapter-base.md`` §実装方針5（アダプタ例外は ``AdapterError`` 派生）
- ``worker/docs/plans/Ph1/05-mufg-csv-adapter.md`` §対象ファイル / §実装方針2〜4
- リスク R-08（文字コード固定、自動判定不採用）
"""

from __future__ import annotations


class AdapterError(Exception):
    """取込アダプタ層が送出する例外の基底。

    機関別アダプタの ``parse`` / ``extract_holdings`` から漏れる例外をこの階層に
    集約することで、CLI 側は ``except AdapterError`` で取込中の入力不整合を
    一括捕捉できる。``Exception`` 直系のままでは ``ValueError``/``KeyError`` 等の
    生例外と区別がつかず、再送可能な失敗（例: 後続行のスキップ）か致命的失敗かの
    判定ができないため、専用基底を設ける。
    """


class EncodingMismatchError(AdapterError):
    """``payload.decode(...)`` が想定エンコーディングで失敗したことを示す。

    chardet 等の自動判定は採用しない方針（R-08）のため、想定外のエンコーディングで
    入ってきた CSV を黙って文字化けさせず、明示例外で早期失敗させる。
    """


class ColumnMissingError(AdapterError):
    """CSV ヘッダに必須列が欠落していることを示す。

    アダプタは Transaction 構築に必要な列のみを必須とする
    （MUFG: 日付 / 摘要 / お支払金額 / お預り金額）。
    銀行 CSV のフォーマット変更を行解析の途中ではなくヘッダ確認段階で検出する。
    """


class MalformedRowError(AdapterError):
    """CSV 行が不正で Transaction を構築できないことを示す。

    数値化不能・日付フォーマット不正・出金/入金の同時記入などを含む。
    生 ``ValueError`` を素通しすると CLI 側で例外区別が困難になるため
    ``AdapterError`` 派生に揃える（plan §実装方針4）。
    """
