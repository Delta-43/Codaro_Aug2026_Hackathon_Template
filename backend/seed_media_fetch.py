"""Fetch royalty-free portrait imagery for the demo seed.

Every image is a Wikimedia Commons file, addressed by its direct
``upload.wikimedia.org`` URL: stable, no API key, no hotlink policy, and a
licence that permits reuse with attribution (written to
``frontend/public/media/CREDITS.md`` alongside the files).

This module is **entirely optional infrastructure**. Nothing in the seed path
depends on it succeeding:

* Files already on disk are never re-downloaded, so re-running is cheap and
  offline-safe once the cache is warm.
* Every fetch is wrapped individually — a 404, a DNS failure or a dead CDN is
  logged and skipped, never raised. ``ensure_media`` cannot fail a reseed.
* A slug with no file on disk simply makes ``seed_media`` return ``None``, and
  ``seed.py`` falls back to its generated SVG gradient.

Run it directly (``python3 backend/seed_media_fetch.py``) or via ``make
fetchmedia``. Seeding calls it only when ``SEED_FETCH_MEDIA=1`` is set.
"""
from __future__ import annotations

import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

# `backend/seed_media_fetch.py` -> repo root -> frontend/public/media
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "media"

# Wikimedia rejects urllib's default User-Agent outright (403), so identify.
_USER_AGENT = "CodaroSeedMedia/1.0 (booking-engine demo seed; +https://example.com/codaro)"
_TIMEOUT = 30
# Wikimedia throttles bursts with a 429. Pace the requests and back off rather
# than hammering — a rate-limited run leaves gaps, and gaps become gradients.
_DELAY = 1.2
_RETRIES = 4

# slug (relative path under the media root, no extension) -> direct image URL.
# Keys must match the slugs in `seed_media.py`; the file lands at
# `<root>/<slug>.jpg`.
SOURCES: dict[str, str] = {
    'avatars/agnieszka-nowak': 'https://upload.wikimedia.org/wikipedia/commons/8/87/Unidentified_young_woman%2C_formal_portrait_%287045670531%29.jpg',
    'avatars/andrzej-stepien': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/1c/Old_man_with_hearing_aid._%28Unsplash%29.jpg/1920px-Old_man_with_hearing_aid._%28Unsplash%29.jpg',
    'avatars/beata-szymanska': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Smiling_woman_%28Unsplash%29.jpg/1920px-Smiling_woman_%28Unsplash%29.jpg',
    'avatars/dorota-sadowska': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/Closed_eye_smile_%28Unsplash%29.jpg/1920px-Closed_eye_smile_%28Unsplash%29.jpg',
    'avatars/elzbieta-kaminska': 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a3/Elderly_Gambian_woman_face_portrait.jpg/1920px-Elderly_Gambian_woman_face_portrait.jpg',
    'avatars/ewa-duda': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Woman_in_glasses_smiling_%28Unsplash%29.jpg/1920px-Woman_in_glasses_smiling_%28Unsplash%29.jpg',
    'avatars/halina-baran': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/Girl_close-up_face_portrait_%2849749906893%29.jpg/1920px-Girl_close-up_face_portrait_%2849749906893%29.jpg',
    'avatars/henryk-walczak': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Chapard._Reproduction_after_watercolour_by_%28B._Y.%29._Wellcome_V0001064.jpg/1920px-Chapard._Reproduction_after_watercolour_by_%28B._Y.%29._Wellcome_V0001064.jpg',
    'avatars/irena-wojcik': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Head_Scarf_%28Unsplash%29.jpg/1920px-Head_Scarf_%28Unsplash%29.jpg',
    'avatars/jan-dabrowski': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/49/Bearded_man_smoking_pipe-3013924.jpg/1920px-Bearded_man_smoking_pipe-3013924.jpg',
    'avatars/katarzyna-lewandowska': 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Portrait_%28Unsplash%29.jpg/1920px-Portrait_%28Unsplash%29.jpg',
    'avatars/krzysztof-malinowski': 'https://upload.wikimedia.org/wikipedia/commons/thumb/b/bf/Gray-haired_man_portrait_%28Unsplash%29.jpg/1920px-Gray-haired_man_portrait_%28Unsplash%29.jpg',
    'avatars/lukas-behrend': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/Face_portrait_%28Unsplash%29.jpg/1920px-Face_portrait_%28Unsplash%29.jpg',
    'avatars/mara-lindqvist': 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d9/Vermeer-Portrait_of_a_Young_Woman.jpg/1920px-Vermeer-Portrait_of_a_Young_Woman.jpg',
    'avatars/marek-kowalczyk': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/9c/Monochrome_bearded_man_%28Unsplash%29.jpg/1920px-Monochrome_bearded_man_%28Unsplash%29.jpg',
    'avatars/michal-sikora': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/Man_with_wrinkles_and_cap_%28Unsplash%29.jpg/1920px-Man_with_wrinkles_and_cap_%28Unsplash%29.jpg',
    'avatars/natalia-krawczyk': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/94/Smiling_Over_Her_Shoulder_%28Unsplash%29.jpg/1920px-Smiling_Over_Her_Shoulder_%28Unsplash%29.jpg',
    'avatars/pawel-gorski': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/16/Curly_hair_and_freckles_man_%28Unsplash%29.jpg/1920px-Curly_hair_and_freckles_man_%28Unsplash%29.jpg',
    'avatars/piotr-zielinski': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Portrait_of_a_man_%28Unsplash%29.jpg/1920px-Portrait_of_a_man_%28Unsplash%29.jpg',
    'avatars/robert-mazur': 'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Man_with_a_white_beard_and_glasses%2C_by_Angelina_Litvin%2C_2015-10-05_%28Unsplash%29.jpg/1920px-Man_with_a_white_beard_and_glasses%2C_by_Angelina_Litvin%2C_2015-10-05_%28Unsplash%29.jpg',
    'avatars/tomasz-wisniewski': 'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Portrait_of_a_Man%2C_Said_to_be_Christopher_Columbus.jpg/1920px-Portrait_of_a_Man%2C_Said_to_be_Christopher_Columbus.jpg',
    'avatars/zofia-adamska': 'https://upload.wikimedia.org/wikipedia/commons/d/d5/A_very_beautiful_old_lady_II_%28443738371%29.jpg',
}

# Attribution per slug, rendered into CREDITS.md next to the files.
CREDITS: dict[str, dict[str, str]] = {
    'avatars/agnieszka-nowak': {
        'title': 'Unidentified young woman, formal portrait (7045670531).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Unidentified_young_woman,_formal_portrait_(7045670531).jpg',
        'license': 'No restrictions',
        'author': 'Mennonite Church USA Archives',
    },
    'avatars/andrzej-stepien': {
        'title': 'Old man with hearing aid. (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Old_man_with_hearing_aid._(Unsplash).jpg',
        'license': 'CC0',
        'author': 'JD Mason',
    },
    'avatars/beata-szymanska': {
        'title': 'Smiling woman (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Smiling_woman_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Allef Vinicius',
    },
    'avatars/dorota-sadowska': {
        'title': 'Closed eye smile (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Closed_eye_smile_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Marcelo Matarazzo',
    },
    'avatars/elzbieta-kaminska': {
        'title': 'Elderly Gambian woman face portrait.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Elderly_Gambian_woman_face_portrait.jpg',
        'license': 'CC BY-SA 2.0',
        'author': 'Ferdinand Reus',
    },
    'avatars/ewa-duda': {
        'title': 'Woman in glasses smiling (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Woman_in_glasses_smiling_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Ehimetalor Unuabona',
    },
    'avatars/halina-baran': {
        'title': 'Girl close-up face portrait (49749906893).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Girl_close-up_face_portrait_(49749906893).jpg',
        'license': 'CC BY 2.0',
        'author': 'Pedro Ribeiro Simões',
    },
    'avatars/henryk-walczak': {
        'title': 'Chapard. Reproduction after watercolour by (B. Y.). Wellcome V0001064.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Chapard._Reproduction_after_watercolour_by_(B._Y.)._Wellcome_V0001064.jpg',
        'license': 'CC BY 4.0',
        'author': 'Antoine Bisetzky (1817-1892)',
    },
    'avatars/irena-wojcik': {
        'title': 'Head Scarf (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Head_Scarf_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Roksolana Zasiadko',
    },
    'avatars/jan-dabrowski': {
        'title': 'Bearded man smoking pipe-3013924.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Bearded_man_smoking_pipe-3013924.jpg',
        'license': 'CC0',
        'author': 'ThuyHaBich',
    },
    'avatars/katarzyna-lewandowska': {
        'title': 'Portrait (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Portrait_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Alesia Kazantceva',
    },
    'avatars/krzysztof-malinowski': {
        'title': 'Gray-haired man portrait (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Gray-haired_man_portrait_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Foto Sushi',
    },
    'avatars/lukas-behrend': {
        'title': 'Face portrait (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Face_portrait_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'William Stitt',
    },
    'avatars/mara-lindqvist': {
        'title': 'Vermeer-Portrait of a Young Woman.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Vermeer-Portrait_of_a_Young_Woman.jpg',
        'license': 'Public domain',
        'author': 'Johannes Vermeer',
    },
    'avatars/marek-kowalczyk': {
        'title': 'Monochrome bearded man (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Monochrome_bearded_man_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Seth Doyle',
    },
    'avatars/michal-sikora': {
        'title': 'Man with wrinkles and cap (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Man_with_wrinkles_and_cap_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Kahar Saidyhalam',
    },
    'avatars/natalia-krawczyk': {
        'title': 'Smiling Over Her Shoulder (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Smiling_Over_Her_Shoulder_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Clem Onojeghuo',
    },
    'avatars/pawel-gorski': {
        'title': 'Curly hair and freckles man (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Curly_hair_and_freckles_man_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Jeremy Bishop',
    },
    'avatars/piotr-zielinski': {
        'title': 'Portrait of a man (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Portrait_of_a_man_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'William Stitt',
    },
    'avatars/robert-mazur': {
        'title': 'Man with a white beard and glasses, by Angelina Litvin, 2015-10-05 (Unsplash).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Man_with_a_white_beard_and_glasses,_by_Angelina_Litvin,_2015-10-05_(Unsplash).jpg',
        'license': 'CC0',
        'author': 'Angelina Litvin',
    },
    'avatars/tomasz-wisniewski': {
        'title': 'Portrait of a Man, Said to be Christopher Columbus.jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:Portrait_of_a_Man,_Said_to_be_Christopher_Columbus.jpg',
        'license': 'Public domain',
        'author': 'Sebastiano del Piombo',
    },
    'avatars/zofia-adamska': {
        'title': 'A very beautiful old lady II (443738371).jpg',
        'page': 'https://commons.wikimedia.org/wiki/File:A_very_beautiful_old_lady_II_(443738371).jpg',
        'license': 'CC BY 2.0',
        'author': 'Pedro Ribeiro Simões',
    },
}

_SUBDIRS = ("avatars", "homes", "arrangements")


def _dest(root: Path, slug: str) -> Path:
    return root / f"{slug}.jpg"


def _looks_like_image(blob: bytes) -> bool:
    """Reject HTML error pages that arrive with a 200."""
    return blob.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF8", b"RIFF"))


def _fetch_one(url: str, dest: Path) -> tuple[bool, str]:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    blob = b""
    for attempt in range(_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                blob = resp.read()
            break
        except urllib.error.HTTPError as exc:
            # 429/503 are transient throttling, not a dead URL — back off.
            if exc.code not in (429, 503) or attempt == _RETRIES - 1:
                raise
            time.sleep(_DELAY * (2 ** attempt) + 2)
    if not blob:
        return False, "empty response"
    if not _looks_like_image(blob):
        return False, "not an image (probably an error page)"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(blob)
    note = _downscale(tmp)
    tmp.replace(dest)  # atomic-ish: a half-written file never looks cached
    return True, f"{dest.stat().st_size // 1024} KiB{note}"


# Avatars render at 40-80px behind `object-cover` on a circle, so the committed
# files are centre-cropped squares at this size. Sources are commonly 1920px
# wide, which is ~700 KB of JPEG per face for pixels nobody sees.
_AVATAR_PX = 512


def _downscale(path: Path) -> str:
    """Shrink a fetched avatar to `_AVATAR_PX`, if Pillow happens to be around.

    Optional on purpose: this module is stdlib-only so `ensure_media` can run
    inside the backend image without adding a dependency for a maintenance
    script. Without Pillow the file is kept at full size, which costs disk and
    nothing else — the browser crops it to the same circle either way.
    """
    if path.parent.name != "avatars":
        return ""
    try:
        from PIL import Image, ImageOps  # noqa: PLC0415
    except ImportError:
        return " (full size: pip install pillow to downscale)"
    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            # The same centre-crop the browser performs, done once, up front.
            im = ImageOps.fit(im, (_AVATAR_PX, _AVATAR_PX), method=Image.LANCZOS)
            im.save(path, "JPEG", quality=82, optimize=True, progressive=True)
    except Exception as exc:  # a bad decode must not fail the fetch
        return f" (kept full size: {exc})"
    return ""


def ensure_media(root: Path | None = None) -> dict:
    """Download any missing demo image into `root`. Never raises.

    Returns a summary dict: ``{"root", "downloaded", "skipped", "failed",
    "bytes", "misses"}``. Callers may log it; nothing should branch on it.
    """
    summary: dict = {
        "root": None, "downloaded": 0, "skipped": 0, "failed": 0,
        "bytes": 0, "misses": [],
    }
    try:
        root = Path(root) if root is not None else DEFAULT_ROOT
        summary["root"] = str(root)
        for sub in _SUBDIRS:
            (root / sub).mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # unwritable path, read-only FS, ...
        logger.warning("seed media: cannot prepare %s (%s) - skipping", root, exc)
        summary["failed"] = len(SOURCES)
        return summary

    for slug, url in SOURCES.items():
        dest = _dest(root, slug)
        try:
            if dest.exists() and dest.stat().st_size > 0:
                summary["skipped"] += 1
                summary["bytes"] += dest.stat().st_size
                continue
            time.sleep(_DELAY)
            ok, note = _fetch_one(url, dest)
            if ok:
                summary["downloaded"] += 1
                summary["bytes"] += dest.stat().st_size
                logger.debug("seed media: %s <- %s (%s)", slug, url, note)
            else:
                summary["failed"] += 1
                summary["misses"].append(f"{slug}: {note}")
        except Exception as exc:  # HTTPError, URLError, socket timeout, OSError
            summary["failed"] += 1
            summary["misses"].append(f"{slug}: {type(exc).__name__}: {exc}")
            try:
                dest.with_suffix(".part").unlink(missing_ok=True)
            except Exception:
                pass

    try:
        write_credits(root)
    except Exception as exc:
        logger.debug("seed media: could not write CREDITS.md (%s)", exc)

    if summary["misses"]:
        logger.info(
            "seed media: %d missing, falling back to generated gradients: %s",
            len(summary["misses"]), "; ".join(summary["misses"][:5]),
        )
    return summary


def maybe_ensure_media(root: Path | None = None) -> dict | None:
    """`ensure_media` gated on ``SEED_FETCH_MEDIA=1``. Safe to call from seeding."""
    if os.getenv("SEED_FETCH_MEDIA", "").strip() not in ("1", "true", "yes", "on"):
        return None
    try:
        return ensure_media(root)
    except Exception as exc:  # belt and braces - a reseed must never die here
        logger.warning("seed media: fetch skipped (%s)", exc)
        return None


def write_credits(root: Path | None = None) -> Path:
    """Write per-file attribution + licence for whatever actually landed."""
    root = Path(root) if root is not None else DEFAULT_ROOT
    lines = [
        "# Media credits",
        "",
        "Every image below is a file from **Wikimedia Commons**, downloaded by",
        "`backend/seed_media_fetch.py` (`make fetchmedia`) and used as demo",
        "portrait imagery for the demo seed. Licences are as recorded on each",
        "file's Commons description page; follow the link for the authoritative",
        "terms and the full author credit.",
        "",
        "| File | Source (Commons) | Author | Licence |",
        "| --- | --- | --- | --- |",
    ]
    for slug in sorted(SOURCES):
        if not _dest(root, slug).exists():
            continue
        c = CREDITS.get(slug, {})
        title = c.get("title", slug).replace("|", "/")
        author = (c.get("author") or "see file page").replace("|", "/")
        page = c.get("page", "")
        link = f"[{title}]({page})" if page else title
        lines.append(f"| `{slug}.jpg` | {link} | {author} | {c.get('license', 'see file page')} |")
    lines.append("")
    dest = root / "CREDITS.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    s = ensure_media()
    print(
        f"media root : {s['root']}\n"
        f"downloaded : {s['downloaded']}\n"
        f"cached     : {s['skipped']}\n"
        f"failed     : {s['failed']}\n"
        f"total size : {s['bytes'] / 1024 / 1024:.1f} MiB"
    )
    for miss in s["misses"]:
        print("  MISS", miss)
    return 0  # a miss is not an error: the seed falls back to gradients


if __name__ == "__main__":
    raise SystemExit(main())
