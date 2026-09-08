# data

written by the [daily workflow](../.github/workflows/daily.yml) at 00:27 utc.

`daily.csv`: one row per coin per utc date. columns: `date_utc`, `block`, `coin`, `quote`,
`pool_fee` (hundredths of a bip, 100 = 0.01%), `spot`, `twap` (10 minutes), `liquidity`
(uniswap's L, comparable within a pair only), `coingecko`, `curve_price` (what 100k of the coin
returns on curve 3pool, per unit; usdt and dai only).

a rerun for the same day replaces that day's rows. columns are only ever appended.
