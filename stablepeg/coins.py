"""the stablecoins, and what they are quoted against."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Coin:
    symbol: str
    address: str
    decimals: int
    coingecko: str


COINS: dict[str, Coin] = {
    c.symbol: c
    for c in (
        Coin("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6, "usd-coin"),
        Coin("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7", 6, "tether"),
        Coin("DAI", "0x6B175474E89094C44Da98b954EedeAC495271d0F", 18, "dai"),
        Coin("USDe", "0x4c9EDD5852cd905f086C759E8383e09bff1E68B3", 18, "ethena-usde"),
        Coin("FRAX", "0x853d955aCEf822Db058eb8505911ED77F175b99e", 18, "frax"),
        Coin("LUSD", "0x5f98805A4E8be255a32880FDeC7F6728C6568bA0", 18, "liquity-usd"),
        Coin("TUSD", "0x0000000000085d4780B73119b644AE5ecd22b376", 18, "true-usd"),
        Coin("PYUSD", "0x6c3ea9036406852006290770BEdFcAbA0e23A0e8", 6, "paypal-usd"),
        Coin("crvUSD", "0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E", 18, "crvusd"),
        Coin("GHO", "0x40D16FC0246aD3160Ccc09B8D0D3A2cD28aE6C2f", 18, "gho"),
        Coin("USDS", "0xdC035D45d973E3EC169d2276DDab16f1e407384F", 18, "usds"),
        Coin("FDUSD", "0xc5f0f7b66764F6ec8C8Dff7BA683102295E16409", 18, "first-digital-usd"),
    )
}
DEFAULT_COINS = ("USDT", "DAI", "USDe", "FRAX", "LUSD", "PYUSD", "crvUSD", "GHO", "USDS")
DEFAULT_QUOTE = "USDC"


def pick(symbols: str | None, quote: str) -> tuple[list[Coin], Coin]:
    lookup = {k.lower(): v for k, v in COINS.items()}
    if quote.lower() not in lookup:
        raise KeyError(quote)
    q = lookup[quote.lower()]
    wanted = [s.strip() for s in (symbols or ",".join(DEFAULT_COINS)).split(",") if s.strip()]
    coins = []
    for s in wanted:
        if s.lower() not in lookup:
            raise KeyError(s)
        c = lookup[s.lower()]
        if c.address.lower() != q.address.lower():
            coins.append(c)
    return coins, q
