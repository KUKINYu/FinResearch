"""API Key 加密存储：Windows DPAPI（CryptProtectData）。

Key 只存本机、只对当前 Windows 用户可解密，不落明文。
macOS/Linux 上退化为 base64（P0 只支持 Windows，仅保证不报错）。
"""

import base64
import ctypes
import sys
from ctypes import wintypes


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _DATA_BLOB:
    buf = ctypes.create_string_buffer(data)
    return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _blob_to_bytes(blob: _DATA_BLOB) -> bytes:
    return ctypes.string_at(blob.pbData, blob.cbData)


def encrypt(plain: str) -> str:
    """加密为可存储字符串（"dpapi:" 前缀标识）。"""
    if plain == "":
        return ""
    if sys.platform != "win32":
        return "plain:" + base64.b64encode(plain.encode("utf-8")).decode()
    data_in = _blob(plain.encode("utf-8"))
    data_out = _DATA_BLOB()
    if ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(data_in), "FinResearch", None, None, None, 0, ctypes.byref(data_out)
    ):
        try:
            return "dpapi:" + base64.b64encode(_blob_to_bytes(data_out)).decode()
        finally:
            ctypes.windll.kernel32.LocalFree(data_out.pbData)
    # DPAPI 失败兜底（不应发生）
    return "plain:" + base64.b64encode(plain.encode("utf-8")).decode()


def decrypt(stored: str) -> str:
    """解密。空串与非密文原样返回。"""
    if not stored:
        return ""
    if stored.startswith("plain:"):
        return base64.b64decode(stored[6:]).decode("utf-8")
    if not stored.startswith("dpapi:"):
        return stored
    if sys.platform != "win32":
        return ""
    raw = base64.b64decode(stored[6:])
    data_in = _DATA_BLOB(len(raw), ctypes.cast(raw, ctypes.POINTER(ctypes.c_char)))
    data_out = _DATA_BLOB()
    if ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(data_in), None, None, None, None, 0, ctypes.byref(data_out)
    ):
        try:
            return _blob_to_bytes(data_out).decode("utf-8")
        finally:
            ctypes.windll.kernel32.LocalFree(data_out.pbData)
    return ""
