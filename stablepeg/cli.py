"""command line entry point: stablepeg [--coins USDT,DAI,...] [--quote USDC] [--twap 600]"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from . import __version__, curve
from .coins import COINS, DEFAULT_QUOTE, pick
from .rpc import Rpc, RpcError, RpcUnavailable
from .uniswap import PoolQuote, best_pool

USER_AGENT = "stablepeg/0.1 (+https://github.com/alinaschanz/stablepeg)"


def coingecko(ids: list[str], timeout: float = 15.0) -> dict[str, float]:
    url = "https://api.coingecko.com/api/v3/simple/price?ids=" + ",".join(sorted(set(ids))) + "&vs_currencies=usd"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    return {k: float(v["usd"]) for k, v in body.items() if "usd" in v}


def bp(price: float | None) -> str:
    if price is None:
        return "n/a"
    return f"{(price - 1) * 10_000:+.1f}bp"


def flag(price: float | None, warn_bp: float) -> str:
    return " !" if price is not None and abs(price - 1) * 10_000 >= warn_bp else ""


def liq(value: int) -> str:
    if value >= 1e18:
        return f"{value / 1e18:.1f}e18"
    if value >= 1e15:
        return f"{value / 1e15:.1f}e15"
    if value >= 1e12:
        return f"{value / 1e12:.1f}e12"
    return f"{value:.2g}"


def table(quotes: list[tuple[str, PoolQuote | None]], quote_symbol: str, cg: dict[str, float], twap: int, warn_bp: float) -> str:
    head = f"{'coin':<7} {'v3 pool':<8} {'spot':>9} {'twap ' + str(twap // 60) + 'm':>9} {'dev':>9} {'liquidity':>10}  {'coingecko':>9}"
    lines = [head]
    for symbol, q in quotes:
        cgp = cg.get(COINS[symbol].coingecko)
        cg_text = f"{cgp:.4f}" if cgp is not None else "n/a"
        if q is None:
            lines.append(f"{symbol:<7} {'no pool':<8} {'-':>9} {'-':>9} {'-':>9} {'-':>10}  {cg_text:>9}")
            continue
        twap_text = f"{q.twap:.5f}" if q.twap is not None else "n/a"
        lines.append(f"{symbol:<7} {q.fee_pct:<8} {q.spot:>9.5f} {twap_text:>9} {bp(q.spot):>9} {liq(q.liquidity):>10}  {cg_text:>9}{flag(q.spot, warn_bp)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="stablepeg", description="are the stablecoins still a dollar? prices read from uniswap v3 and curve on mainnet.")
    ap.add_argument("--coins", metavar="SYMBOLS", help=f"comma separated, from: {', '.join(COINS)} (default: the usual suspects)")
    ap.add_argument("--quote", default=DEFAULT_QUOTE, help=f"what to price against (default {DEFAULT_QUOTE})")
    ap.add_argument("--twap", type=int, default=600, help="twap window in seconds, 0 to skip (default 600)")
    ap.add_argument("--size", type=float, default=100_000, help="curve 3pool swap size for the effective price (default 100,000)")
    ap.add_argument("--warn", type=float, default=50, help="flag deviations of at least this many basis points (default 50)")
    ap.add_argument("--json", action="store_true", help="json instead of the table")
    ap.add_argument("--no-coingecko", action="store_true", help="skip the coingecko comparison column")
    ap.add_argument("--no-curve", action="store_true", help="skip the curve 3pool lines")
    ap.add_argument("--rpc", action="append", metavar="URL", help="json-rpc endpoint (repeatable, tried in order)")
    ap.add_argument("--version", action="version", version=f"stablepeg {__version__}")
    args = ap.parse_args(argv)

    try:
        coins, quote = pick(args.coins, args.quote)
    except KeyError as exc:
        print(f"error: unknown coin {exc}, pick from {', '.join(COINS)}", file=sys.stderr)
        return 2
    rpc = Rpc(args.rpc) if args.rpc else Rpc()
    cg: dict[str, float] = {}
    if not args.no_coingecko:
        try:
            cg = coingecko([c.coingecko for c in coins] + [quote.coingecko])
        except Exception as exc:  # noqa: BLE001
            print(f"warning: coingecko unavailable ({exc})", file=sys.stderr)
    try:
        block = rpc.block_number()
        stamp = datetime.fromtimestamp(rpc.block_timestamp(block), tz=timezone.utc)
        with ThreadPoolExecutor(max_workers=4) as pool:
            quotes = list(zip([c.symbol for c in coins], pool.map(lambda c: best_pool(rpc, c, quote, args.twap), coins)))
        swaps = []
        vp = None
        if not args.no_curve:
            for sym_in in ("USDT", "DAI"):
                if sym_in != quote.symbol and quote.symbol in curve.INDEX:
                    swaps.append(curve.quote(rpc, sym_in, quote.symbol, args.size))
            vp = curve.virtual_price(rpc)
    except (RpcError, RpcUnavailable) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "block": block, "time_utc": stamp.isoformat(), "quote": quote.symbol,
            "pools": [{
                "coin": s, "pool": q.pool if q else None, "fee": q.fee if q else None, "spot": q.spot if q else None,
                "twap": q.twap if q else None, "liquidity": q.liquidity if q else None,
                "coingecko": cg.get(COINS[s].coingecko),
            } for s, q in quotes],
            "curve_3pool": [{"in": s.coin_in.symbol, "out": s.coin_out.symbol, "amount_in": s.amount_in,
                             "amount_out": s.amount_out, "price": s.price} for s in swaps],
            "curve_virtual_price": vp,
        }, indent=2))
        return 0

    print(f"stablecoins vs {quote.symbol} on ethereum mainnet, block {block:,} ({stamp:%Y-%m-%d %H:%M} utc)")
    if quote.coingecko in cg:
        print(f"{quote.symbol} itself: ${cg[quote.coingecko]:.4f} on coingecko")
    print()
    print(table(quotes, quote.symbol, cg, args.twap, args.warn))
    if swaps:
        print()
        parts = [f"{s.amount_in:,.0f} {s.coin_in.symbol} -> {s.amount_out:,.0f} {s.coin_out.symbol} ({bp(s.price)})" for s in swaps]
        print("curve 3pool: " + ", ".join(parts) + (f", virtual price {vp:.4f}" if vp else ""))
    flagged = [s for s, q in quotes if q and abs(q.spot - 1) * 10_000 >= args.warn]
    print()
    print("! = at least %g bp off the peg: %s" % (args.warn, ", ".join(flagged)) if flagged else f"nothing is more than {args.warn:g} bp off the peg")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
