# changelog

all notable changes to stablepeg. the format follows [keep a changelog](https://keepachangelog.com/en/1.1.0/),
versions follow [semver](https://semver.org/) as far as a command line tool has an api.

## [unreleased]

## [0.1.0] - 2026-09-08

first cut: stablecoin pegs from uniswap v3 and curve, next to coingecko.

- deepest uniswap v3 pool per coin: spot from `slot0`, twap from `observe`
- curve 3pool quote for a 100k swap, coingecko next to it, deviation in bp
- 12 coins checked against the chain by the live test
