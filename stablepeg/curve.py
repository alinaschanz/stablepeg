"""curve 3pool (dai / usdc / usdt): what a real-sized swap would actually return."""
from __future__ import annotations

from dataclasses import dataclass

from . import abi
from .coins import COINS, Coin
from .rpc import Rpc

THREE_POOL = "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7"
INDEX = {"DAI": 0, "USDC": 1, "USDT": 2}


@dataclass
class Swap:
    coin_in: Coin
    coin_out: Coin
    amount_in: float
    amount_out: float

    @property
    def price(self) -> float:
        return self.amount_out / self.amount_in if self.amount_in else 0.0


def get_dy(rpc: Rpc, i: int, j: int, dx: int) -> int:
    return abi.uint(rpc.eth_call(THREE_POOL, abi.calldata("get_dy(int128,int128,uint256)", abi.word(i), abi.word(j), abi.word(dx))))


def quote(rpc: Rpc, sym_in: str, sym_out: str, amount: float) -> Swap:
    cin, cout = COINS[sym_in], COINS[sym_out]
    dx = int(amount * 10 ** cin.decimals)
    dy = get_dy(rpc, INDEX[sym_in], INDEX[sym_out], dx)
    return Swap(cin, cout, amount, dy / 10 ** cout.decimals)


def virtual_price(rpc: Rpc) -> float:
    return abi.uint(rpc.eth_call(THREE_POOL, abi.calldata("get_virtual_price()"))) / 1e18
