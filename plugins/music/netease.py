import re
from dataclasses import dataclass, field

import httpx

API_HEADERS = {
    "Referer": "https://music.163.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}

SEARCH_URL = "https://music.163.com/api/search/get/web"
SONG_DETAIL_URL = "https://music.163.com/api/song/detail"

URL_RE = re.compile(r"https?://\S+")
SONG_ID_RE = re.compile(r"song(?:\?id=|/)(\d+)")


@dataclass
class Song:
    id: int
    name: str
    artists: list[str] = field(default_factory=list)
    album: str = ""

    @property
    def artist_text(self) -> str:
        return " / ".join(a for a in self.artists if a) or "未知歌手"


def _parse_song(item: dict) -> Song | None:
    song_id = item.get("id")
    if not song_id:
        return None
    artists_raw = item.get("artists") or item.get("ar") or []
    album_raw = item.get("album") or item.get("al") or {}
    return Song(
        id=int(song_id),
        name=item.get("name", ""),
        artists=[a.get("name", "") for a in artists_raw if isinstance(a, dict)],
        album=album_raw.get("name", "") if isinstance(album_raw, dict) else "",
    )


async def search_songs(keyword: str, limit: int = 5) -> list[Song]:
    """搜索歌曲，返回候选列表"""
    async with httpx.AsyncClient(
        headers=API_HEADERS, timeout=10, follow_redirects=True
    ) as client:
        resp = await client.get(
            SEARCH_URL,
            params={"s": keyword, "type": 1, "offset": 0, "total": "true", "limit": limit},
        )
        resp.raise_for_status()
        data = resp.json()

    songs = []
    for item in data.get("result", {}).get("songs", [])[:limit]:
        song = _parse_song(item)
        if song:
            songs.append(song)
    return songs


async def get_song(song_id: int) -> Song | None:
    """获取单曲详情"""
    async with httpx.AsyncClient(
        headers=API_HEADERS, timeout=10, follow_redirects=True
    ) as client:
        resp = await client.get(SONG_DETAIL_URL, params={"ids": f"[{song_id}]"})
        resp.raise_for_status()
        data = resp.json()

    items = data.get("songs") or []
    if not items:
        return None
    return _parse_song(items[0])


def _extract_song_id_from_url(url: str) -> int | None:
    if "music.163.com" not in url:
        return None
    match = SONG_ID_RE.search(url)
    return int(match.group(1)) if match else None


async def extract_song_id(text: str) -> int | None:
    """从文本中提取网易云歌曲 ID，支持普通链接、#/song?id= 形式及 163cn.tv 短链"""
    direct = _extract_song_id_from_url(text)
    if direct:
        return direct

    url_match = URL_RE.search(text) or re.search(r"\S*163cn\.tv/\S+", text)
    if not url_match:
        return None
    url = url_match.group(0)
    if "163cn.tv" not in url:
        return _extract_song_id_from_url(url)

    async with httpx.AsyncClient(
        headers=API_HEADERS, timeout=10, follow_redirects=True
    ) as client:
        resp = await client.get(url if url.startswith("http") else f"https://{url}")
        return _extract_song_id_from_url(str(resp.url))
