"""Spike B 第一步：从巨潮资讯网下载 5 份真实 A 股招股说明书。

用法：engine/.venv 的 python 运行（仅用标准库，无新依赖）。
数据来源：巨潮资讯网（证监会指定信息披露网站），公开信息，用于技术验证。
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT_DIR = Path(__file__).parent / "data"
SEARCH_URL = "http://www.cninfo.com.cn/new/fulltextSearch/full"
PDF_BASE = "http://static.cninfo.com.cn/"

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "http://www.cninfo.com.cn/new/fulltextSearch",
}


def search(page: int, page_size: int = 30) -> list[dict]:
    body = urllib.parse.urlencode(
        {
            "searchkey": "招股说明书",
            "sdate": "",
            "edate": "",
            "isfulltext": "false",
            "sortName": "pubdate",
            "sortType": "desc",
            "pageNum": str(page),
        }
    )
    req = urllib.request.Request(SEARCH_URL, data=body.encode(), headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8")).get("announcements") or []


def is_a_share_ipo(a: dict) -> bool:
    """过滤：A 股首发招股说明书（排除 H 股、发行公告、上市公告书等）。"""
    title = a.get("announcementTitle", "")
    return (
        "首次公开发行股票并在" in title
        and "招股说明书" in title
        and "H股" not in title
        and "公告" not in title
    )


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
        f.write(resp.read())


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    picked: list[dict] = []
    for page in range(1, 6):
        if len(picked) >= 5:
            break
        for a in search(page):
            if is_a_share_ipo(a):
                picked.append(a)
                if len(picked) >= 5:
                    break
        time.sleep(0.5)

    if len(picked) < 5:
        print(f"只找到 {len(picked)} 份，请调整过滤条件", file=sys.stderr)
        return 1

    for a in picked:
        code, name = a["secCode"], a["secName"]
        url = PDF_BASE + a["adjunctUrl"]
        dest = OUT_DIR / f"{code}_{name}_招股说明书.pdf"
        print(f"下载 {name}({code}) ... ", end="", flush=True)
        try:
            download(url, dest)
            size_mb = dest.stat().st_size / 1024 / 1024
            print(f"OK {size_mb:.1f}MB")
        except Exception as e:  # noqa: BLE001 下载失败不中断，报告即可
            print(f"失败 {e}")

    print("\n完成，文件在", OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
