"""compose config 出力を扱うテスト共通ユーティリティ。

複数のテストモジュールから ``docker compose config`` 出力の
サービスブロック抽出を行うため、ここに公開ヘルパとして集約する。
本ファイルは pytest のテスト収集対象外（``test_`` プレフィックスを持たない）。

YAML パーサ（PyYAML）を導入すれば堅牢だが、テスト専用の依存を増やしたく
ないため、軽量な正規表現でブロック抽出を行う方針をとる。
"""

from __future__ import annotations

import re


def extract_service_block(config_text: str, service_name: str) -> str | None:
    """compose config 出力から特定サービスのブロックを抽出する。

    docker compose config の出力では各サービスは indent 2 で `  <name>:` と
    始まり、配下のフィールドは indent 4 以上で続く。次のサービス境界は
    再び `\\n  <英字始まりの名前>:` のパターンになる。
    """
    pattern = rf"\n  {re.escape(service_name)}:\n"
    match = re.search(pattern, config_text)
    if match is None:
        return None
    start = match.end()
    # 次の indent2 のサービス境界を探す。compose config は alphabetical 順で
    # サービスを列挙し、各サービスは `\n  <name>:\n` で始まる。
    next_match = re.search(r"\n  [a-z][a-z0-9_-]*:\n", config_text[start:])
    if next_match is None:
        return config_text[start:]
    return config_text[start : start + next_match.start()]
