"""uniswap v3: find the deepest pool for a pair, read the spot price and a short twap.

price maths, for the record: sqrtPriceX96 is sqrt(token1 raw units per token0 raw unit) times 2^96,
so token1-per-token0 in human units is (sqrtPriceX96 / 2^96)^2 * 10^(decimals0 - decimals1).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from fractions import Fraction

from . import abi
from .coins import Coin
from .rpc import Rpc, RpcError

FACTORY = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
FEE_TIERS = (100, 500, 3000, 10000)
ZERO = "0x" + "0" * 40
Q96 = 1 << 96


@dataclass
class PoolQuote:
    coin: Coin
    quote: Coin
    pool: str
    fee: int  # in hundredths of a bip: 100 = 0.01%
    liquidity: int
    spot: float  # quote units per one coin
    twap: float | None = None  # same, averaged over the twap window

    @property
    def fee_pct(self) -> str:
        return f"{self.fee / 10_000:g}%"


def price_from_sqrt(sqrt_price_x96: int, dec0: int, dec1: int) -> Fraction:
    """token1 per token0, human units."""
    raw = Fraction(sqrt_price_x96 * sqrt_price_x96, Q96 * Q96)
    return raw * Fraction(10 ** dec0, 10 ** dec1)


def price_from_tick(tick: int, dec0: int, dec1: int) -> float:
    return (1.0001 ** tick) * 10 ** (dec0 - dec1)


def oriented(coin: Coin, quote: Coin) -> tuple[Coin, Coin, bool]:
    """(token0, token1, coin_is_token0) - uniswap sorts the pair by address."""
    if coin.address.lower() < quote.address.lower():
        return coin, quote, True
    return quote, coin, False


def get_pool(rpc: Rpc, a: Coin, b: Coin, fee: int) -> str | None:
    data = abi.calldata("getPool(address,address,uint24)", abi.address_word(a.address), abi.address_word(b.address), abi.word(fee))
    out = rpc.eth_call(FACTORY, data)
    if len(out) < 32:
        return None
    pool = abi.address(out)
    return None if pool == ZERO else pool


def liquidity(rpc: Rpc, pool: str) -> int:
    return abi.uint(rpc.eth_call(pool, abi.calldata("liquidity()")))


def slot0(rpc: Rpc, pool: str) -> tuple[int, int]:
    out = rpc.eth_call(pool, abi.calldata("slot0()"))
    return abi.uint(out, 0), abi.sint(out, 1)


def twap_tick(rpc: Rpc, pool: str, seconds: int) -> int | None:
    data = abi.calldata("observe(uint32[])", abi.word(0x20), abi.word(2), abi.word(seconds), abi.word(0))
    try:
        out = rpc.eth_call(pool, data)
    except RpcError:  # "OLD": the pool has too few observations for that window
        return None
    cumulative = abi.int_array(out, 0)
    if len(cumulative) != 2:
        return None
    return (cumulative[1] - cumulative[0]) // seconds  # floor, like the periphery library


def quote_pool(rpc: Rpc, coin: Coin, quote: Coin, pool: str, fee: int, twap_seconds: int, liq: int | None = None) -> PoolQuote:
    token0, token1, coin_is_0 = oriented(coin, quote)
    sqrt_price, _tick = slot0(rpc, pool)
    p = price_from_sqrt(sqrt_price, token0.decimals, token1.decimals)  # token1 per token0
    spot = float(p) if coin_is_0 else float(1 / p) if p else 0.0
    twap = None
    if twap_seconds > 0:
        tick = twap_tick(rpc, pool, twap_seconds)
        if tick is not None:
            t = price_from_tick(tick, token0.decimals, token1.decimals)
            twap = t if coin_is_0 else (1 / t if t else 0.0)
    return PoolQuote(coin=coin, quote=quote, pool=pool, fee=fee, liquidity=liquidity(rpc, pool) if liq is None else liq,
                     spot=spot, twap=twap)


def _pool_and_liquidity(rpc: Rpc, coin: Coin, quote: Coin, fee: int) -> tuple[int, str | None, int]:
    pool = get_pool(rpc, coin, quote, fee)
    return fee, pool, (liquidity(rpc, pool) if pool else 0)


def best_pool(rpc: Rpc, coin: Coin, quote: Coin, twap_seconds: int = 600, fee_tiers=FEE_TIERS) -> PoolQuote | None:
    """the pool with the most liquidity across the fee tiers, quoted. the tiers are looked up in parallel."""
    with ThreadPoolExecutor(max_workers=len(fee_tiers)) as pool:
        found = list(pool.map(lambda fee: _pool_and_liquidity(rpc, coin, quote, fee), fee_tiers))
    live = [(liq, addr, fee) for fee, addr, liq in found if addr and liq]
    if not live:
        return None
    liq, addr, fee = max(live)
    return quote_pool(rpc, coin, quote, addr, fee, twap_seconds, liq=liq)
