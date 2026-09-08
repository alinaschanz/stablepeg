"""offline: abi encoding, uniswap price maths, pool selection and the table with a fake node."""
import csv
import json
from fractions import Fraction

from stablepeg import abi, cli, curve, uniswap
from stablepeg.coins import COINS, pick
from stablepeg.uniswap import Q96, oriented, price_from_sqrt, price_from_tick

USDC, USDT, DAI, WETH_DEC = COINS["USDC"], COINS["USDT"], COINS["DAI"], 18


def test_selectors_and_calldata():
    assert abi.calldata("slot0()") == "0x3850c7bd"
    data = abi.calldata("getPool(address,address,uint24)", abi.address_word(USDC.address), abi.address_word(USDT.address), abi.word(100))
    assert data.startswith("0x1698ee82") and len(data) == 2 + 8 + 64 * 3
    assert data.endswith("64")  # fee 100 = 0x64


def test_signed_and_array_decoding():
    neg = (-5) & abi.MASK256
    assert abi.sint(neg.to_bytes(32, "big")) == -5
    # observe(...) style answer: two dynamic arrays, the first with two signed values
    head = abi.word(0x40) + abi.word(0xA0)
    arr1 = abi.word(2) + abi.word(-100) + abi.word(200)
    arr2 = abi.word(2) + abi.word(1) + abi.word(2)
    data = bytes.fromhex(head + arr1 + arr2)
    assert abi.int_array(data, 0) == [-100, 200]
    assert abi.int_array(data, 1) == [1, 2]


def test_string_decoding_both_shapes():
    dyn = bytes.fromhex(abi.word(0x20) + abi.word(4)) + b"USDC".ljust(32, b"\x00")
    assert abi.string(dyn) == "USDC"
    assert abi.string(b"MKR".ljust(32, b"\x00")) == "MKR"


def test_price_from_sqrt_one_to_one_same_decimals():
    assert price_from_sqrt(Q96, 6, 6) == 1


def test_price_from_sqrt_usdc_weth_example():
    # usdc (6) is token0, weth (18) token1; at 2500 usdc per eth the raw ratio is 1e12/2500 = 4e8
    sqrt_price = 20_000 * Q96  # sqrt(4e8) = 20000
    p = price_from_sqrt(sqrt_price, 6, WETH_DEC)  # weth per usdc
    assert p == Fraction(1, 2500)
    assert abs(price_from_tick(0, 6, 6) - 1.0) < 1e-12


def test_oriented_sorts_by_address():
    t0, t1, coin_is_0 = oriented(USDT, USDC)
    assert (t0, t1) == (USDC, USDT) and coin_is_0 is False
    t0, t1, coin_is_0 = oriented(DAI, USDC)
    assert (t0, t1) == (DAI, USDC) and coin_is_0 is True


def test_pick_and_quote():
    coins, quote = pick(None, "USDC")
    assert quote is USDC and USDC not in coins and coins[0] is USDT
    coins, quote = pick("usdc,dai", "usdt")
    assert [c.symbol for c in coins] == ["USDC", "DAI"] and quote is USDT


class FakeRpc:
    """answers eth_call by selector; liquidity per pool address."""

    def __init__(self):
        self.pools = {100: "0x" + "a1" * 20, 500: "0x" + "a5" * 20}
        self.liquidity = {"0x" + "a1" * 20: 10**18, "0x" + "a5" * 20: 5 * 10**18}

    def eth_call(self, to, data, block="latest"):
        sel = data[2:10]
        if sel == abi.SEL["getPool(address,address,uint24)"]:
            fee = int(data[-64:], 16)
            pool = self.pools.get(fee)
            return bytes.fromhex(abi.address_word(pool) if pool else abi.word(0))
        if sel == abi.SEL["liquidity()"]:
            return bytes.fromhex(abi.word(self.liquidity[to]))
        if sel == abi.SEL["slot0()"]:
            sqrt_price = int((Fraction(1_000_500, 1_000_000) ** Fraction(1, 2)) * Q96) if to.endswith("a5" * 20) else Q96
            return bytes.fromhex(abi.word(sqrt_price) + abi.word(0) + abi.word(0) * 5)
        if sel == abi.SEL["observe(uint32[])"]:
            ticks = abi.word(2) + abi.word(0) + abi.word(600 * 3)
            seconds = abi.word(2) + abi.word(0) + abi.word(0)
            return bytes.fromhex(abi.word(0x40) + abi.word(0xA0) + ticks + seconds)
        if sel == abi.SEL["get_dy(int128,int128,uint256)"]:
            dx = int(data[-64:], 16)
            return bytes.fromhex(abi.word(dx - dx // 10_000))  # 1 bp of slippage, same decimals
        if sel == abi.SEL["get_virtual_price()"]:
            return bytes.fromhex(abi.word(int(1.0389 * 1e18)))
        raise AssertionError(sel)

    def block_number(self):
        return 25_000_000

    def block_timestamp(self, number):
        return 1_757_289_600


def test_best_pool_prefers_liquidity_and_orients_the_price():
    q = uniswap.best_pool(FakeRpc(), USDT, USDC, twap_seconds=600)
    assert q.fee == 500 and q.pool.endswith("a5" * 20)
    # usdc is token0 for usdc/usdt, so the raw price is usdt per usdc = 1.0005 -> usdt in usdc = 1/1.0005
    assert abs(q.spot - 1 / 1.0005) < 1e-6
    assert abs(q.twap - 1 / (1.0001 ** 3)) < 1e-9


def test_curve_quote_uses_pool_indexes():
    s = curve.quote(FakeRpc(), "USDT", "USDC", 100_000)
    assert s.amount_in == 100_000 and abs(s.amount_out - 99_990) < 1e-6 and abs(s.price - 0.9999) < 1e-9


def test_cli_table_and_json(monkeypatch, capsys):
    monkeypatch.setattr(cli, "Rpc", lambda urls=None: FakeRpc())
    monkeypatch.setattr(cli, "coingecko", lambda ids: {"tether": 1.0002, "usd-coin": 0.9999})
    assert cli.main(["--coins", "USDT", "--warn", "1"]) == 0
    out = capsys.readouterr().out
    assert "USDT    0.05%" in out and "-5.0bp" in out and "!" in out and "curve 3pool: 100,000 USDT -> 99,990 USDC" in out
    assert cli.main(["--coins", "USDT", "--json", "--no-curve"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["quote"] == "USDC" and doc["pools"][0]["fee"] == 500 and doc["curve_3pool"] == []


def test_summary_append_replaces_the_day(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "Rpc", lambda urls=None: FakeRpc())
    monkeypatch.setattr(cli, "coingecko", lambda ids: {"tether": 1.0002, "usd-coin": 0.9999})
    path = tmp_path / "daily.csv"
    assert cli.main(["--coins", "USDT", "--summary-append", str(path), "--quiet"]) == 0
    assert capsys.readouterr().out == ""
    assert cli.main(["--coins", "USDT", "--summary-append", str(path), "--quiet"]) == 0
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]["coin"] == "USDT" and rows[0]["pool_fee"] == "500" and rows[0]["curve_price"].startswith("0.9999")
    cli.append_summary(str(path), [{"date_utc": "2024-01-01", "block": 1, "coin": "DAI", "quote": "USDC", "pool_fee": 100, "spot": "1",
                                    "twap": "", "liquidity": 1, "coingecko": "", "curve_price": ""}])
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    keys = [(r["date_utc"], r["coin"]) for r in rows]
    assert keys == sorted(keys) and len(keys) == 2 and keys[0] == ("2024-01-01", "DAI") and keys[1][1] == "USDT"


def test_cli_rejects_unknown_coin():
    assert cli.main(["--coins", "DOGE"]) == 2


def test_formatting_helpers():
    assert cli.bp(1.0) == "+0.0bp" and cli.bp(0.995) == "-50.0bp" and cli.bp(None) == "n/a"
    assert cli.liq(3 * 10**18) == "3.0e18" and cli.liq(123) == "1.2e+02"
