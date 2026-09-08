# stablepeg

[![ci](https://github.com/alinaschanz/stablepeg/actions/workflows/ci.yml/badge.svg)](https://github.com/alinaschanz/stablepeg/actions/workflows/ci.yml)
![python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)
![license mit](https://img.shields.io/badge/license-MIT-2b7a74)
[![release](https://img.shields.io/github/v/release/alinaschanz/stablepeg?color=2b7a74)](https://github.com/alinaschanz/stablepeg/releases)

are the stablecoins still a dollar? for each coin: spot and a 10 minute twap from its
deepest uniswap v3 pool against usdc, what a 100k swap returns on curve 3pool, and the
coingecko price next to it for a sanity check. everything but the last column is read
straight from ethereum mainnet over a public rpc. no keys, nothing to install.

```
$ stablepeg
stablecoins vs USDC on ethereum mainnet, block 25,929,333 (2026-09-08 01:22 utc)
USDC itself: $0.9999 on coingecko

coin    v3 pool       spot  twap 10m       dev  liquidity  coingecko
USDT    0.01%      0.99998   1.00000    -0.2bp    25.0e15     0.9999
DAI     0.01%      1.00001   1.00000    +0.1bp  9108.4e18     0.9998
USDe    0.01%      0.99997   0.99990    -0.3bp  4973.2e18     0.9997
FRAX    0.05%      0.99164   0.99164   -83.6bp    11.4e18     0.9921 !
LUSD    0.05%      1.00889   1.00884   +88.9bp    11.9e15     1.0090 !
PYUSD   0.01%      1.00004   1.00000    +0.4bp   709.8e12     0.9998
crvUSD  0.3%       1.00167   1.00170   +16.7bp   526.0e15     0.9999
GHO     0.01%      0.99902   0.99900    -9.8bp    54.6e18     0.9990
USDS    0.3%       0.99877   0.99880   -12.3bp     6.0e18     0.9998

curve 3pool: 100,000 USDT -> 99,987 USDC (-1.3bp), 100,000 DAI -> 99,985 USDC (-1.5bp), virtual price 1.0398

! = at least 50 bp off the peg: FRAX, LUSD
```

usdt, dai and usde inside one basis point is what "pegged" looks like. frax and lusd at
80-90 bp is not news, they trade like that most weeks; the flag is there so a real
depeg would not hide in a wall of numbers.

## install

```
pipx install git+https://github.com/alinaschanz/stablepeg
```

or clone it and run `python -m stablepeg` from the folder. python 3.10 or newer, no dependencies.

## use

```
stablepeg                                       # the usual suspects against usdc
stablepeg --coins USDT,DAI,FDUSD,TUSD --quote USDT
stablepeg --twap 1800 --size 1000000            # 30 minute twap, 1m curve swap
stablepeg --warn 20                             # flag at 20 bp
stablepeg --depth                               # what a 100k / 1m / 10m sale returns, impact in bp (quoter v2)
stablepeg --json
stablepeg --no-coingecko --no-curve             # chain only
stablepeg --summary-append data/daily.csv --quiet   # one row per coin, the daily dataset
```

coins on offer: USDC, USDT, DAI, USDe, FRAX, LUSD, TUSD, PYUSD, crvUSD, GHO, USDS, FDUSD.
the live test checks each address against `symbol()` and `decimals()` on chain, and the
curve pool coin order against `coins(i)`.

## how it works

- [uniswap v3 factory](https://etherscan.io/address/0x1F98431c8aD98523631AE4a59f267346ea31F984)
  `getPool(a, b, fee)` for the 0.01%, 0.05%, 0.3% and 1% tiers; the pool with the most
  `liquidity()` wins. `slot0().sqrtPriceX96` is the spot price:
  token1 per token0 = (sqrtPriceX96 / 2^96)^2 x 10^(dec0 - dec1), flipped when the coin is token1.
- `observe([600, 0])` gives tick cumulatives; their difference over the window, floored, is
  the mean tick, and 1.0001^tick is the twap. pools with too few observations answer
  "OLD" and get `n/a`.
- [curve 3pool](https://etherscan.io/address/0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7)
  `get_dy(i, j, dx)` for a 100k swap is an effective price with the fee in it, which is
  the number a real seller gets. `get_virtual_price()` is printed for the curious.
- [coingecko simple price](https://www.coingecko.com/en/api) for the last column; skip it with `--no-coingecko`.
- every call is an `eth_call` over json-rpc via `urllib`; endpoints publicnode, drpc,
  mevblocker, tenderly, blastapi in that order, or `--rpc` yours. the fee tiers and the
  coins are fetched in parallel.

`--depth` asks the [uniswap quoter v2](https://etherscan.io/address/0x61fFE014bA17989E743c5F6cB21bF9697530B21e)
what selling 100k, 1m and 10m of the coin into the same pool would return; the impact is the
effective price against the spot. a peg that holds for 100k and breaks at 10m is the interesting case.
this is one uniswap pool: for dai and the newer coins most of the depth lives on curve and in the
maker psm, so a big impact here reads as "not on uniswap", not as "depegged".

## reading the table

- `dev` is spot minus one in basis points. `!` marks at least `--warn` bp (default 50).
- `liquidity` is uniswap's L (sqrt of x times y in raw units). it is only comparable within
  a pair, so read it as "which tier the price came from", not as a ranking of coins.
- a 0.01% pool with real liquidity and a twap that agrees with the spot is a price you
  can trust. a 1% pool with a wide gap between spot and twap is a thin market, and the
  coingecko column will usually disagree with it.

## the dataset

`data/daily.csv` gets one row per coin every night at 00:27 utc (spot, twap, pool, coingecko,
curve): a small peg history that anyone can plot. columns are described in
[data/README.md](data/README.md); a rerun for the same day replaces the day.

## see also

- [bigmoves](https://github.com/alinaschanz/bigmoves): the large transfers of these coins
- [onchain-notes](https://github.com/alinaschanz/onchain-notes), [gasweek](https://github.com/alinaschanz/gasweek), [ens-lookup](https://github.com/alinaschanz/ens-lookup)
- the notes: [alinaschanz.life](https://alinaschanz.life), the short version on [x](https://x.com/alinaschanz)

## license

[mit](LICENSE). numbers, not calls. not financial advice.
