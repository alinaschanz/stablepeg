"""the few abi helpers this needs. selectors are the first four bytes of keccak256 of the
signature; they are written out here so nothing has to be hashed at runtime."""
from __future__ import annotations

SEL = {
    "getPool(address,address,uint24)": "1698ee82",
    "slot0()": "3850c7bd",
    "liquidity()": "1a686502",
    "observe(uint32[])": "883bdbfd",
    "token0()": "0dfe1681",
    "token1()": "d21220a7",
    "fee()": "ddca3f43",
    "decimals()": "313ce567",
    "symbol()": "95d89b41",
    "get_dy(int128,int128,uint256)": "5e0d443f",
    "get_virtual_price()": "bb7b8b80",
    "coins(uint256)": "c6610657",
}

MASK256 = (1 << 256) - 1


def word(value: int) -> str:
    return (value & MASK256).to_bytes(32, "big").hex()


def address_word(address: str) -> str:
    return address[2:].lower().rjust(64, "0")


def calldata(signature: str, *words: str) -> str:
    return "0x" + SEL[signature] + "".join(words)


def uint(data: bytes, index: int = 0) -> int:
    return int.from_bytes(data[32 * index:32 * index + 32], "big")


def sint(data: bytes, index: int = 0) -> int:
    v = uint(data, index)
    return v - (1 << 256) if v >> 255 else v


def address(data: bytes, index: int = 0) -> str:
    return "0x" + data[32 * index + 12:32 * index + 32].hex()


def string(data: bytes) -> str:
    """abi string, with the bytes32 fallback a few old tokens use for symbol()."""
    if len(data) == 32:
        return data.rstrip(b"\x00").decode("utf-8", errors="replace")
    offset = uint(data, 0)
    length = int.from_bytes(data[offset:offset + 32], "big")
    return data[offset + 32:offset + 32 + length].decode("utf-8", errors="replace")


def int_array(data: bytes, index: int) -> list[int]:
    """dynamic array of signed ints whose offset sits in head word `index`."""
    offset = uint(data, index)
    length = int.from_bytes(data[offset:offset + 32], "big")
    body = data[offset + 32:]
    return [sint(body, i) for i in range(length)]
