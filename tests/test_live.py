"""talks to a public rpc. skipped unless STABLEPEG_LIVE=1."""
import os

import pytest

from stablepeg import abi, curve, uniswap
from stablepeg.coins import COINS
from stablepeg.rpc import Rpc

pytestmark = pytest.mark.skipif(os.environ.get("STABLEPEG_LIVE") != "1", reason="set STABLEPEG_LIVE=1")


def test_coin_table_matches_the_chain():
    rpc = Rpc()
    for coin in COINS.values():
        symbol = abi.string(rpc.eth_call(coin.address, abi.calldata("symbol()")))
        decimals = abi.uint(rpc.eth_call(coin.address, abi.calldata("decimals()")))
        assert symbol == coin.symbol, (coin.symbol, symbol)
        assert decimals == coin.decimals, (coin.symbol, decimals)


def test_usdt_usdc_pool_is_near_a_dollar():
    q = uniswap.best_pool(Rpc(), COINS["USDT"], COINS["USDC"], twap_seconds=600)
    assert q is not None and 0.9 < q.spot < 1.1
    assert q.twap is None or 0.9 < q.twap < 1.1


def test_curve_3pool_coins_are_in_the_expected_order():
    rpc = Rpc()
    for symbol, index in curve.INDEX.items():
        got = abi.address(rpc.eth_call(curve.THREE_POOL, abi.calldata("coins(uint256)", abi.word(index))))
        assert got == COINS[symbol].address.lower()
