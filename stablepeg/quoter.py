"""uniswap v3 quoter v2: what a swap of a given size would actually return, straight from the pool maths.

`quoteExactInputSingle` is not a view function but it reverts-with-data on purpose so it can be called
with eth_call; quoter v2 wraps that and answers normally.
"""
from __future__ import annotations

from . import abi
from .coins import Coin
from .rpc import Rpc

QUOTER_V2 = "0x61fFE014bA17989E743c5F6cB21bF9697530B21e"
SEL_QUOTE = "c6a5026a"  # quoteExactInputSingle((address,address,uint256,uint24,uint160))
SIZES = (100_000, 1_000_000, 10_000_000)


def quote_exact_input_single(rpc: Rpc, token_in: str, token_out: str, fee: int, amount_in: int) -> int:
    data = "0x" + SEL_QUOTE + abi.address_word(token_in) + abi.address_word(token_out) + abi.word(amount_in) + abi.word(fee) + abi.word(0)
    out = rpc.eth_call(QUOTER_V2, data)
    return abi.uint(out, 0)


def depth(rpc: Rpc, coin: Coin, quote: Coin, fee: int, sizes=SIZES) -> list[tuple[int, float]]:
    """(size in coin units, effective price in quote units per coin) for each size, through one pool."""
    out = []
    for size in sizes:
        amount_in = int(size) * 10 ** coin.decimals
        got = quote_exact_input_single(rpc, coin.address, quote.address, fee, amount_in)
        out.append((int(size), (got / 10 ** quote.decimals) / size if size else 0.0))
    return out


def impact_bp(effective: float, spot: float) -> float:
    return (effective / spot - 1) * 10_000 if spot else 0.0
