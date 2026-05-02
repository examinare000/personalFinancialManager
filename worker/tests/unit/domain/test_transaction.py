"""``Transaction`` ドメイン型と ``compute_hash`` の単体テスト（TDD Red 段階）。

検証範囲:
- ``Transaction`` の正常系インスタンス化（10 フィールド + frozen + slots）
- ``__post_init__`` の異常系バリデーション
  （``amount`` / ``currency`` / ``occurred_on`` / ``occurred_at``）
- ``compute_hash`` の決定性（同一引数で繰り返し同値、引数差分で別値）
- ``compute_hash`` の正規化規約
  （``f"{account_id}|{occurred_on.isoformat()}|{amount}|{description}"`` の SHA256 hex）

設計準拠:
- ``postgres/docs/plans/Ph1/03-domain-types.md`` §実装方針 / 受入条件 / テスト計画
- ``docs/adr/006-hash-uniqueness.md`` §決定（4 引数 SHA256 hex）
- ``docs/adr/005-decimal-monetary-precision.md``（amount は Decimal 固定）

テストは TDD の Red 段階で先行作成する。実装は後続ステップで追加する。
"""

from __future__ import annotations

import dataclasses
import hashlib
from datetime import date, datetime
from decimal import Decimal

import pytest

# ---------------------------------------------------------------------------
# 正常系 — 10 フィールドの dataclass を frozen + slots で生成できる
# ---------------------------------------------------------------------------


def _正常な引数() -> dict[str, object]:
    """異常系テストの「他は正常」状態を作るための共通辞書。"""
    return {
        "account_id": 1,
        "occurred_on": date(2026, 4, 30),
        "occurred_at": datetime(2026, 4, 30, 12, 34, 56),
        "amount": Decimal("1234.56"),
        "currency": "JPY",
        "description": "コンビニ",
        "category_id": None,
        "category_source": None,
        "raw_payload": {"source": "csv", "row": 1},
        "hash": "0" * 64,
    }


def test_Transactionは10フィールドを保持する正常系で生成できる() -> None:
    """plan §実装方針2 の 10 フィールド構成で問題なくインスタンス化できることを確認する。"""
    from kakeibo_shared.domain import Transaction

    tx = Transaction(**_正常な引数())  # type: ignore[arg-type]

    assert tx.account_id == 1
    assert tx.occurred_on == date(2026, 4, 30)
    assert tx.occurred_at == datetime(2026, 4, 30, 12, 34, 56)
    assert tx.amount == Decimal("1234.56")
    assert tx.currency == "JPY"
    assert tx.description == "コンビニ"
    assert tx.category_id is None
    assert tx.category_source is None
    assert tx.raw_payload == {"source": "csv", "row": 1}
    assert tx.hash == "0" * 64


def test_Transaction_amountはDecimal型である() -> None:
    """受入条件1: ``isinstance(tx.amount, Decimal) is True``。

    ADR-005 の通貨精度方針を Python 層で型レベルに固定する。
    """
    from kakeibo_shared.domain import Transaction

    tx = Transaction(**_正常な引数())  # type: ignore[arg-type]
    assert isinstance(tx.amount, Decimal)


def test_Transaction_occurred_atにはNoneも渡せる() -> None:
    """受入条件2: ``occurred_at: Optional[datetime]``。

    取込元（例: 残高 PDF）が時刻を持たないケースを通すため None を許容する。
    """
    from kakeibo_shared.domain import Transaction

    args = _正常な引数()
    args["occurred_at"] = None
    tx = Transaction(**args)  # type: ignore[arg-type]
    assert tx.occurred_at is None


def test_Transactionはfrozenで属性更新できない() -> None:
    """plan §実装方針1: ``@dataclass(frozen=True, slots=True)``。

    ハッシュキーとなり得る値の事後変更を不変条件として禁じる。
    """
    from kakeibo_shared.domain import Transaction

    tx = Transaction(**_正常な引数())  # type: ignore[arg-type]
    with pytest.raises(dataclasses.FrozenInstanceError):
        tx.amount = Decimal("999.00")  # type: ignore[misc]


def test_Transactionはslotsで未定義属性を拒む() -> None:
    """``slots=True`` の効果として、宣言外の属性追加が ``AttributeError`` になる。

    ``__dict__`` の不在を直接検証することで slots 適用の事実を確認する。
    """
    from kakeibo_shared.domain import Transaction

    tx = Transaction(**_正常な引数())  # type: ignore[arg-type]
    assert not hasattr(tx, "__dict__")


# ---------------------------------------------------------------------------
# 異常系 — plan §実装方針3 の 3 種バリデーション + 受入条件4 の8件以上
# ---------------------------------------------------------------------------


def test_Transactionはamount_NoneでValueErrorを出す() -> None:
    """plan §実装方針3 / §受入条件4: ``amount=None`` を弾く。"""
    from kakeibo_shared.domain import Transaction

    args = _正常な引数()
    args["amount"] = None
    with pytest.raises(ValueError):
        Transaction(**args)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("invalid_currency", "理由"),
    [
        ("JP", "長さ 2（< 3）"),
        ("JPYY", "長さ 4（> 3）"),
        ("", "空文字"),
        ("jpy", "小文字"),
        ("Jpy", "大小混在"),
        ("JP1", "数字混入（isalpha 違反）"),
        ("JP ", "空白混入（isalpha 違反）"),
    ],
)
def test_Transactionは不正な通貨コードでValueErrorを出す(invalid_currency: str, 理由: str) -> None:
    """plan §実装方針3 / §受入条件4: ``len==3 and isalpha and isupper`` 以外を ValueError で弾く。

    ISO 4217 風の 3 文字英大文字以外はすべて拒否する。
    ``理由`` 引数は失敗ケース identifier として可読性のために残す。
    """
    from kakeibo_shared.domain import Transaction

    args = _正常な引数()
    args["currency"] = invalid_currency
    with pytest.raises(ValueError):
        Transaction(**args)  # type: ignore[arg-type]


def test_Transactionは通貨コードがstr以外ならTypeErrorを出す() -> None:
    """``validate_currency_code`` が ``isinstance(code, str)`` を強制すること。

    ``int`` のような型で渡された場合、``len()`` 等で曖昧なエラーを出す前に
    早期に TypeError を出す（Fail Fast）。
    """
    from kakeibo_shared.domain import Transaction

    args = _正常な引数()
    args["currency"] = 392  # JPY の ISO 4217 数字コードを誤って渡したケース
    with pytest.raises(TypeError):
        Transaction(**args)  # type: ignore[arg-type]


def test_Transactionはoccurred_onが文字列ならTypeErrorを出す() -> None:
    """plan §実装方針3 / §受入条件4: 文字列の ISO8601 を date に自動変換しない（明示要求）。"""
    from kakeibo_shared.domain import Transaction

    args = _正常な引数()
    args["occurred_on"] = "2026-04-30"
    with pytest.raises(TypeError):
        Transaction(**args)  # type: ignore[arg-type]


def test_Transactionはoccurred_onがNoneならTypeErrorを出す() -> None:
    """受入条件: ``occurred_on=None`` を ``ValueError`` または ``TypeError`` で弾く。

    plan §実装方針3 では「``occurred_on`` が ``date`` でないなら ``TypeError``」と規定。
    """
    from kakeibo_shared.domain import Transaction

    args = _正常な引数()
    args["occurred_on"] = None
    with pytest.raises(TypeError):
        Transaction(**args)  # type: ignore[arg-type]


def test_Transactionはoccurred_onがdatetimeでもdateサブクラスとして許容する() -> None:
    """``datetime`` は ``date`` のサブクラスなので ``isinstance(_, date)`` は True。

    実装が ``type(_) is date`` で判定すると ``datetime`` を誤って弾いてしまう。
    plan §3 の規定は ``isinstance(_, date)`` であり、``datetime`` を許容する。
    本テストは厳格判定回帰の早期検出に使う。
    """
    from kakeibo_shared.domain import Transaction

    args = _正常な引数()
    args["occurred_on"] = datetime(2026, 4, 30, 0, 0, 0)
    tx = Transaction(**args)  # type: ignore[arg-type]
    assert isinstance(tx.occurred_on, date)


def test_Transactionはoccurred_atが非datetimeならTypeErrorを出す() -> None:
    """受入条件「``occurred_at: Optional[datetime]``」を実行時に保証する。

    None と ``datetime`` 以外（``date`` 単独や文字列など）はバリデーション対象。
    plan §実装方針2 で ``occurred_at: Optional[datetime]`` と明示されている。
    """
    from kakeibo_shared.domain import Transaction

    args = _正常な引数()
    args["occurred_at"] = date(2026, 4, 30)  # date は datetime ではない
    with pytest.raises(TypeError):
        Transaction(**args)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# compute_hash — plan §実装方針4 / §受入条件4 / §テスト計画2
# ---------------------------------------------------------------------------


def test_compute_hashは正規化規約どおりのSHA256_hexを返す() -> None:
    """plan §実装方針4 の正規化文字列をテスト側で再構築してクロスチェックする。

    マジックな 16 進数文字列の直書きを避け、決定性そのものを検証する。
    """
    from kakeibo_shared.domain import compute_hash

    canonical = f"1|{date(2026, 4, 30).isoformat()}|{Decimal('1234.56')}|コンビニ"
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    actual = compute_hash(1, date(2026, 4, 30), Decimal("1234.56"), "コンビニ")
    assert actual == expected
    # SHA256 hex は 64 文字の 16 進数。
    assert len(actual) == 64
    assert all(c in "0123456789abcdef" for c in actual)


def test_compute_hashは100回呼んでも同じ値を返す() -> None:
    """plan §テスト計画2: 決定性。プロセス内で 100 回反復しても同値であること。

    ハッシュ化対象に環境依存（時刻・乱数・ロケール）が混入しないことの回帰検出。
    """
    from kakeibo_shared.domain import compute_hash

    base = compute_hash(1, date(2026, 4, 30), Decimal("1234.56"), "コンビニ")
    for _ in range(100):
        assert compute_hash(1, date(2026, 4, 30), Decimal("1234.56"), "コンビニ") == base


def test_compute_hashはaccount_idが変わると別値になる() -> None:
    from kakeibo_shared.domain import compute_hash

    a = compute_hash(1, date(2026, 4, 30), Decimal("1234.56"), "コンビニ")
    b = compute_hash(2, date(2026, 4, 30), Decimal("1234.56"), "コンビニ")
    assert a != b


def test_compute_hashはoccurred_onが変わると別値になる() -> None:
    from kakeibo_shared.domain import compute_hash

    a = compute_hash(1, date(2026, 4, 30), Decimal("1234.56"), "コンビニ")
    b = compute_hash(1, date(2026, 5, 1), Decimal("1234.56"), "コンビニ")
    assert a != b


def test_compute_hashはamountが変わると別値になる() -> None:
    from kakeibo_shared.domain import compute_hash

    a = compute_hash(1, date(2026, 4, 30), Decimal("1234.56"), "コンビニ")
    b = compute_hash(1, date(2026, 4, 30), Decimal("1234.57"), "コンビニ")
    assert a != b


def test_compute_hashはdescriptionが変わると別値になる() -> None:
    from kakeibo_shared.domain import compute_hash

    a = compute_hash(1, date(2026, 4, 30), Decimal("1234.56"), "コンビニ")
    b = compute_hash(1, date(2026, 4, 30), Decimal("1234.56"), "スーパー")
    assert a != b


def test_compute_hashはdescriptionをトリミングしない() -> None:
    """plan §実装方針4: description のトリミング・正規化は Phase 1.7 まで延期。

    ここで前後空白を吸収すると、Phase 1.7 で導入する正規化との二重処理になる。
    """
    from kakeibo_shared.domain import compute_hash

    trimmed = compute_hash(1, date(2026, 4, 30), Decimal("1234.56"), "コンビニ")
    padded = compute_hash(1, date(2026, 4, 30), Decimal("1234.56"), " コンビニ ")
    assert trimmed != padded


def test_compute_hashはDecimal表現の差を別値として扱う() -> None:
    """plan §実装方針4 の正規化文字列は ``str(amount)`` を用いる。

    ``Decimal("1234.56")`` と ``Decimal("1234.560")`` は数値的には等価だが、
    plan の正規化規約は文字列表現を採用しているため別ハッシュになる。
    本テストは正規化規約の固定（暗黙の正規化を入れないこと）を保証する。
    """
    from kakeibo_shared.domain import compute_hash

    a = compute_hash(1, date(2026, 4, 30), Decimal("1234.56"), "コンビニ")
    b = compute_hash(1, date(2026, 4, 30), Decimal("1234.560"), "コンビニ")
    assert a != b
