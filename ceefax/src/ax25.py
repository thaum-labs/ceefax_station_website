from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple


FLAG_BYTE = 0x7E
UI_CONTROL = 0x03
NO_LAYER3_PID = 0xF0


def _parse_callsign(s: str) -> Tuple[str, int]:
    """
    Parse "CALL" or "CALL-SSID" into (CALL, ssid_int).
    """
    raw = (s or "").strip().upper()
    if "-" in raw:
        call, ssid_s = raw.split("-", 1)
        try:
            ssid = int(ssid_s)
        except ValueError:
            ssid = 0
        return (call.strip(), max(0, min(15, ssid)))
    return (raw, 0)


def encode_address_field(callsign: str, *, last: bool) -> bytes:
    """
    Encode a single AX.25 address (7 bytes) for callsign "CALL" or "CALL-SSID".

    - Callsign: 6 chars, padded with spaces, uppercased, each ASCII char << 1
    - SSID byte: bits 6..5 set to 1 (0x60), ssid in bits 4..1, bit0 = end-of-address
      We keep C and H bits cleared.
    """
    call, ssid = _parse_callsign(callsign)
    call = call[:6].ljust(6)
    out = bytearray()
    for ch in call:
        out.append((ord(ch) & 0x7F) << 1)

    ssid_byte = 0x60 | ((ssid & 0x0F) << 1) | (0x01 if last else 0x00)
    out.append(ssid_byte)
    return bytes(out)


def crc16_x25(data: bytes) -> int:
    """
    CRC-16/X.25 (aka CRC-16/IBM-SDLC reflected):
      init=0xFFFF, poly=0x8408, xorout=0xFFFF
    """
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return (~crc) & 0xFFFF


def build_ui_frame(*, dest: str, src: str, info: bytes) -> bytes:
    """
    Build an AX.25 UI frame WITHOUT flags.
    Returns: address+control+pid+info+fcs (fcs little-endian bytes).
    """
    addr = encode_address_field(dest, last=False) + encode_address_field(src, last=True)
    body = addr + bytes([UI_CONTROL, NO_LAYER3_PID]) + (info or b"")
    fcs = crc16_x25(body)
    return body + bytes([fcs & 0xFF, (fcs >> 8) & 0xFF])


def bytes_to_bits_lsb(data: bytes) -> List[int]:
    bits: List[int] = []
    for b in data:
        for i in range(8):
            bits.append((b >> i) & 1)
    return bits


def bit_stuff(bits: Iterable[int]) -> List[int]:
    """
    Insert a 0 after any run of five consecutive 1 bits.
    """
    out: List[int] = []
    ones = 0
    for bit in bits:
        out.append(int(bit))
        if bit:
            ones += 1
            if ones == 5:
                out.append(0)
                ones = 0
        else:
            ones = 0
    return out


def flag_bits() -> List[int]:
    return bytes_to_bits_lsb(bytes([FLAG_BYTE]))


@dataclass(frozen=True)
class Fragment:
    page: str
    subpage: int
    index: int
    total: int
    payload: bytes


def build_fragment_header_v1(page: str, subpage: int, index: int, total: int) -> bytes:
    """
    Header v1:
      b'CFX1' + page(3 ascii) + subpage(2 ascii) + index(1 byte) + total(1 byte)
    """
    p = (page or "000")[:3].rjust(3, "0")
    sp = str(max(0, subpage))[-2:].rjust(2, "0")
    return b"CFX1" + p.encode("ascii") + sp.encode("ascii") + bytes([index & 0xFF, total & 0xFF])


def build_fragment_header_v2(
    *,
    tx_id_bytes: bytes,
    page: str,
    subpage: int,
    index: int,
    total: int,
) -> bytes:
    """
    Header v2:
      b'CFX2' + tx_id(16 bytes) + page(3 ascii) + subpage(2 ascii) + index(1) + total(1)
    """
    if len(tx_id_bytes) != 16:
        raise ValueError("tx_id_bytes must be 16 bytes (UUID bytes)")
    p = (page or "000")[:3].rjust(3, "0")
    sp = str(max(0, subpage))[-2:].rjust(2, "0")
    return (
        b"CFX2"
        + tx_id_bytes
        + p.encode("ascii")
        + sp.encode("ascii")
        + bytes([index & 0xFF, total & 0xFF])
    )


def fragment_page_bytes(
    *,
    tx_id_bytes: bytes | None = None,
    page: str,
    subpage: int,
    page_bytes: bytes,
    max_info_bytes: int,
) -> List[Fragment]:
    """
    Split page_bytes into multiple UI-frame info payloads.
    """
    header_len = 0
    if tx_id_bytes is not None:
        header_len = len(build_fragment_header_v2(tx_id_bytes=tx_id_bytes, page=page, subpage=subpage, index=0, total=0))
    else:
        header_len = len(build_fragment_header_v1(page, subpage, 0, 0))
    max_payload = max(1, max_info_bytes - header_len)
    chunks = [page_bytes[i : i + max_payload] for i in range(0, len(page_bytes), max_payload)]
    total = max(1, len(chunks))
    frags: List[Fragment] = []
    for i, chunk in enumerate(chunks):
        if tx_id_bytes is not None:
            hdr = build_fragment_header_v2(
                tx_id_bytes=tx_id_bytes,
                page=page,
                subpage=subpage,
                index=i,
                total=total,
            )
        else:
            hdr = build_fragment_header_v1(page, subpage, i, total)
        frags.append(Fragment(page=page, subpage=subpage, index=i, total=total, payload=hdr + chunk))
    return frags

