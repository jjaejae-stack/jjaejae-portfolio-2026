#!/usr/bin/env python3
"""
Portfolio Builder local helper server.

Runs the "Generate" button in builder.html: the browser page is still opened
normally via file://, and only talks to this server for two things it can't
do on its own —
  1. POST /generate   asks the locally-installed `claude` CLI to draft
     copy (title / category / client line / body paragraphs) for a project.
  2. GET  /scan-images lists real image files in a folder next to this
     script, so a project can be auto-linked to its photo folder.

Usage:  python3 server.py   (then click "Generate" in the builder — no
API key needed, it shells out to the `claude` CLI using your existing
Claude Code login.)
"""
import base64
import hashlib
import html as html_lib
import http.server
import io
import json
import os
import re
import subprocess
import tempfile
import unicodedata
import urllib.parse

from PIL import Image, ImageSequence

PORT = 8420
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_HTML_PATH = os.path.join(BASE_DIR, "index.html")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v"}
MAX_IMAGE_DIM = 2000
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_TIMEOUT_SEC = 180
MAX_BUDGET_USD = "0.50"

VAULT_DIR = "/Users/cheil/Desktop/Portfolio Wiki"
VOICE_PATH = os.path.join(VAULT_DIR, "voice.md")
INBOX_SAMPLE_PATH = os.path.join(VAULT_DIR, "inbox", "내가 쓴 글.md")
PORTFOLIO_DIR = os.path.join(VAULT_DIR, "portfolio")


def _read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def load_voice_rulebook():
    """voice.md, inserted whole into every /generate prompt as the style rulebook."""
    return _read_file(VOICE_PATH)


def load_voice_examples():
    """Approved portfolio/*.md posts take priority as tone examples; otherwise fall
    back to inbox/내가 쓴 글.md (the raw source voice.md's rules were derived from)."""
    try:
        approved = sorted(
            fn for fn in os.listdir(PORTFOLIO_DIR)
            if fn.lower().endswith(".md") and os.path.isfile(os.path.join(PORTFOLIO_DIR, fn))
        )
    except OSError:
        approved = []
    if approved:
        parts = [_read_file(os.path.join(PORTFOLIO_DIR, fn)) for fn in approved]
        return "\n\n---\n\n".join(p for p in parts if p), "portfolio/"
    return _read_file(INBOX_SAMPLE_PATH), "inbox/내가 쓴 글.md"

GENERATE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "tag": {"type": "string"},
        "meta": {"type": "string"},
        "heading": {"type": "string"},
        "paragraphs": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["title", "tag", "meta", "heading", "paragraphs"]
}

INFO_GENERATE_SCHEMA = {
    "type": "object",
    "properties": {
        "lead": {"type": "string"},
        "paragraphs": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["lead", "paragraphs"]
}

TRANSLATE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "tag": {"type": "string"},
        "meta": {"type": "string"},
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "heading": {"type": "string"},
                    "paragraphs": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["heading", "paragraphs"]
            }
        }
    },
    "required": ["title", "tag", "meta", "blocks"]
}

INFO_TRANSLATE_SCHEMA = {
    "type": "object",
    "properties": {
        "lead": {"type": "string"},
        "paragraphs": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["lead", "paragraphs"]
}


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def find_project_folder(name):
    """Best-effort: look for a subfolder of BASE_DIR matching the project name.
    macOS stores filenames in NFD (decomposed) Unicode, so a Korean title typed
    into index.html/builder (NFC) won't byte-match os.listdir() results unless
    both sides are normalized first."""
    if not name:
        return None
    candidates = [name, name.strip(), name.upper(), name.replace(" ", "")]
    candidates = [unicodedata.normalize("NFC", c) for c in candidates]
    try:
        entries = [e for e in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, e))]
    except OSError:
        return None
    entries_nfc = {unicodedata.normalize("NFC", e): e for e in entries}
    for c in candidates:
        if c in entries_nfc:
            return entries_nfc[c]
    lowered = name.lower()
    for e in entries:
        if unicodedata.normalize("NFC", e).lower() == lowered:
            return e
    return None


def list_images(folder):
    """Recursively collect image files under BASE_DIR/folder, return relative paths."""
    root = os.path.join(BASE_DIR, folder)
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in IMAGE_EXT:
                rel = os.path.relpath(os.path.join(dirpath, fn), BASE_DIR)
                out.append(rel.replace(os.sep, "/"))
    out.sort(key=natural_key)
    return out


def list_videos(folder):
    """Recursively collect video files under BASE_DIR/folder, return relative paths
    (used by the builder's "폴더에서 선택" video picker, so an already-optimized video
    can be attached to another block without re-uploading/re-encoding it)."""
    root = os.path.join(BASE_DIR, folder)
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in VIDEO_EXT:
                rel = os.path.relpath(os.path.join(dirpath, fn), BASE_DIR)
                out.append(rel.replace(os.sep, "/"))
    out.sort(key=natural_key)
    return out


def _sanitize_folder(folder):
    """A project's inferred upload folder can come from its title (builder.html's
    inferProjectFolder() falls back to the title for a brand-new project's first
    upload, before any image has a real relPath to infer a folder from) — and titles
    routinely contain literal newlines for multi-line display (e.g. "Samsung\nNeo
    QLED 8K :\nOnly for Neo Owners."). A raw newline in a folder name is a valid
    Unix filename byte, so os.makedirs happily creates it, but the resulting relPath
    is not a usable URL path segment and the image 404s everywhere it's used.
    Collapse all whitespace runs (including newlines) into a single space before
    it ever becomes part of a path, matching how the title reads as one line
    elsewhere in the UI. """
    return re.sub(r"\s+", " ", (folder or "").strip()).strip("/")


def _unique_path(out_dir, name_noext, ext, suffix="-crop"):
    candidate = name_noext + suffix + ext
    n = 2
    while os.path.exists(os.path.join(out_dir, candidate)):
        candidate = name_noext + suffix + str(n) + ext
        n += 1
    return candidate


def _unique_plain_path(out_dir, name_noext, ext):
    """Like _unique_path but keeps the original filename when there's no
    collision, only appending "-2", "-3", ... if something else is already
    sitting at that exact name."""
    candidate = name_noext + ext
    n = 2
    while os.path.exists(os.path.join(out_dir, candidate)):
        candidate = name_noext + "-" + str(n) + ext
        n += 1
    return candidate


def _resize_cap(img, max_dim=MAX_IMAGE_DIM):
    """Downscale (never upscale) so neither dimension exceeds max_dim, preserving
    aspect ratio — like optimize_video's ffmpeg scale filter, but for stills. Runs
    on every freshly-uploaded photo so a full-res camera/design export never ships
    at full size just because nobody remembered to resize it first."""
    w, h = img.size
    if max(w, h) <= max_dim:
        return img
    scale = max_dim / float(max(w, h))
    return img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)


def _resize_cap_frames(frames, max_dim=MAX_IMAGE_DIM):
    """Same as _resize_cap but for a list of animated-GIF frames, which must all
    end up at the same size (resized together, judged by the first frame)."""
    if not frames:
        return frames
    w, h = frames[0].size
    if max(w, h) <= max_dim:
        return frames
    scale = max_dim / float(max(w, h))
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    return [f.resize(size, Image.LANCZOS) for f in frames]


def crop_image(payload):
    """Crop an image on disk (or freshly-uploaded bytes) and save the result
    as a new file next to the source, so the original is never overwritten.
    Runs entirely server-side because cropping via <canvas> in the browser
    fails with a "tainted canvas" SecurityError for file:// images."""
    x = int(round(payload.get("x", 0)))
    y = int(round(payload.get("y", 0)))
    w = int(round(payload.get("width", 0)))
    h = int(round(payload.get("height", 0)))
    if w <= 0 or h <= 0:
        raise ValueError("잘라낼 영역 크기가 올바르지 않습니다.")

    mode = payload.get("mode") or "relPath"
    if mode == "relPath":
        rel_path = (payload.get("relPath") or "").strip()
        if not rel_path:
            raise ValueError("relPath가 필요합니다.")
        abs_path = os.path.normpath(os.path.join(BASE_DIR, rel_path))
        if not (abs_path + os.sep).startswith(BASE_DIR + os.sep):
            raise ValueError("허용되지 않는 경로입니다.")
        if not os.path.isfile(abs_path):
            raise ValueError("원본 파일을 찾을 수 없습니다: %s" % rel_path)
        folder = os.path.dirname(rel_path)
        base_name = os.path.basename(rel_path)
        img = Image.open(abs_path)
    else:
        data_url = payload.get("dataUrl") or ""
        if "," not in data_url:
            raise ValueError("dataUrl이 올바르지 않습니다.")
        raw = base64.b64decode(data_url.split(",", 1)[1])
        img = Image.open(io.BytesIO(raw))
        folder = _sanitize_folder(payload.get("folder"))
        base_name = (payload.get("filename") or "cropped.png").strip() or "cropped.png"

    name_noext, ext = os.path.splitext(base_name)
    if not ext:
        ext = ".jpg"

    img_w, img_h = img.size
    x = max(0, min(x, img_w - 1))
    y = max(0, min(y, img_h - 1))
    w = max(1, min(w, img_w - x))
    h = max(1, min(h, img_h - y))
    box = (x, y, x + w, y + h)

    out_dir = os.path.join(BASE_DIR, folder) if folder else BASE_DIR
    os.makedirs(out_dir, exist_ok=True)
    out_name = _unique_path(out_dir, name_noext, ext)
    out_abs = os.path.join(out_dir, out_name)
    out_rel = (folder + "/" + out_name) if folder else out_name

    is_animated_gif = img.format == "GIF" and getattr(img, "is_animated", False)
    if is_animated_gif:
        frames = []
        durations = []
        for frame in ImageSequence.Iterator(img):
            frames.append(frame.convert("RGBA").crop(box))
            durations.append(frame.info.get("duration", 100))
        frames = _resize_cap_frames(frames)
        frames[0].save(
            out_abs, save_all=True, append_images=frames[1:],
            loop=img.info.get("loop", 0), duration=durations, disposal=2,
        )
        out_w, out_h = frames[0].size
    else:
        cropped = _resize_cap(img.crop(box))
        save_kwargs = {}
        if ext.lower() in (".jpg", ".jpeg"):
            if cropped.mode not in ("RGB", "L"):
                cropped = cropped.convert("RGB")
            save_kwargs["quality"] = 100
        elif ext.lower() == ".webp":
            save_kwargs["quality"] = 100
        cropped.save(out_abs, **save_kwargs)
        out_w, out_h = cropped.size

    return {"relPath": out_rel, "width": out_w, "height": out_h}


def _run_ffmpeg(input_source, out_abs, trim_start=None, trim_end=None):
    # Cap the LONGER edge at 1920 (not just width) so portrait video is capped by
    # height instead of width — the old "scale=min(1920,iw):-2" only ever capped
    # width, so a portrait 4K clip (e.g. 2160x3840) got scaled to 1920x3413 instead
    # of a proper 1080p-equivalent (1080x1920). Anything already at/under a 1920
    # long edge (including a normal 1080p or 1080x1920 vertical clip) passes through
    # with no resize at all — full resolution preserved, only re-encoded.
    scale_filter = "scale='if(gt(iw,ih),min(1920,iw),-2)':'if(gt(iw,ih),-2,min(1920,ih))'"
    cmd = ["ffmpeg", "-y", "-i", input_source]
    # -ss/-to as OUTPUT options (after -i) are both interpreted against the ORIGINAL
    # input timeline, so trim_start/trim_end are plain absolute seconds into the
    # source video — frame-accurate (unlike -ss before -i, which seeks to the
    # nearest keyframe) since we're already re-encoding the whole file regardless.
    if trim_start is not None:
        cmd += ["-ss", str(trim_start)]
    if trim_end is not None:
        cmd += ["-to", str(trim_end)]
    cmd += [
        "-vf", scale_filter,
        # crf 18 + preset slow: visually near-lossless x264 (crf 23/medium noticeably
        # softened fine detail/motion on portfolio footage) — bigger files, but this
        # runs once at upload time on a local machine, so the extra encode time is cheap.
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        out_abs,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg 인코딩 실패: " + proc.stderr.strip()[-1500:])


def _poster_path_for(video_abs):
    """비디오 파일 경로 옆에 나란히 둘 썸네일 JPG 경로 — 이름 충돌을 피하려고 "-poster.jpg"
    접미사를 붙임(우연히 같은 이름의 실제 업로드 사진과 안 겹치게)."""
    base, _ext = os.path.splitext(video_abs)
    return base + "-poster.jpg"


def _extract_poster(video_abs):
    """인코딩(또는 재다듬기) 직후 첫 프레임 근처를 썸네일 JPG로 뽑아 옆에 저장 — <video>의
    poster 속성으로 써서, 재생 누르기 전까지 화면이 새까맣게 나오던 문제(특히 사파리)를
    없앰. 실패해도(아주 짧은 영상 등) 조용히 무시 — poster가 없으면 그냥 예전처럼 보일
    뿐 재생 자체엔 영향 없음."""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", "0", "-i", video_abs, "-frames:v", "1", "-q:v", "3", _poster_path_for(video_abs)],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        pass


def _video_cache_path():
    return os.path.join(BASE_DIR, ".video_cache.json")


def _load_video_cache():
    try:
        with open(_video_cache_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_video_cache(cache):
    try:
        with open(_video_cache_path(), "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def optimize_video_from_bytes(raw, folder, filename, trim_start=None, trim_end=None):
    """Core of the upload path: re-encode raw video bytes to a web-friendly H.264/AAC
    mp4 with faststart, server-side via ffmpeg, and cache the result by content hash
    (sha256 of the raw bytes) in .video_cache.json — reusing the same source video
    (e.g. the hero video picked again for a block) reuses the already-encoded file
    instead of re-encoding and writing a duplicate onto disk.

    Called directly by the /optimize-video-raw route (video bytes streamed straight
    from the request body — no base64/JSON involved, so multi-hundred-MB phone-shot
    vertical videos don't have to be held in memory as a giant base64 string first,
    which is what was crashing the browser tab on large uploads) and, for backward
    compatibility, by optimize_video()'s legacy dataUrl JSON path.

    trim_start/trim_end (seconds, optional) cut the clip during the SAME encode pass
    instead of a separate step — trimming folds into the optimize pipeline for free.
    The cache key incorporates the trim range so a trimmed clip never collides with
    (or gets served in place of) the untrimmed original, or a different trim of the
    same source file."""
    folder = _sanitize_folder(folder)
    filename = (filename or "video").strip() or "video"
    name_noext = os.path.splitext(filename)[0] or "video"

    out_dir = os.path.join(BASE_DIR, folder) if folder else BASE_DIR
    os.makedirs(out_dir, exist_ok=True)

    content_hash = hashlib.sha256(raw).hexdigest()
    if trim_start is not None or trim_end is not None:
        content_hash += ":trim:%s-%s" % (trim_start, trim_end)
    cached = _load_video_cache().get(content_hash)
    if cached and os.path.isfile(os.path.join(BASE_DIR, cached["relPath"])):
        return {"relPath": cached["relPath"], "width": cached.get("width"), "height": cached.get("height"), "reused": True}

    out_name = _unique_path(out_dir, name_noext, ".mp4", suffix="-web")
    out_abs = os.path.join(out_dir, out_name)
    out_rel = (folder + "/" + out_name) if folder else out_name

    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1] or ".mp4", delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name
    try:
        _run_ffmpeg(tmp_path, out_abs, trim_start=trim_start, trim_end=trim_end)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    _extract_poster(out_abs)

    width, height = _probe_video_dims(out_abs)

    cache = _load_video_cache()
    cache[content_hash] = {"relPath": out_rel, "width": width, "height": height}
    _save_video_cache(cache)

    return {"relPath": out_rel, "width": width, "height": height}


def _probe_video_dims(out_abs):
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "json", out_abs],
            capture_output=True, text=True, timeout=30,
        )
        streams = json.loads(probe.stdout).get("streams") or []
        if streams:
            return streams[0].get("width"), streams[0].get("height")
    except Exception:
        pass
    return None, None


def trim_video_existing(payload):
    """Re-trim an ALREADY-SAVED video in place by relPath — the "다듬기" button on a
    video that's already been uploaded, as opposed to trimming during the initial
    upload (see optimize_video_from_bytes's trim_start/trim_end, which folds
    trimming into the very first encode instead). Re-encodes into a temp file in
    the same directory, then atomically replaces the original so relPath (and every
    project that references it) never has to change — no new file, no orphaned
    duplicate. Re-trims an already-encoded file, so repeated trims of the same clip
    lose a little quality each time (the pre-optimization source isn't kept around
    to trim from instead) — the same tradeoff any editor without a non-destructive
    history makes; acceptable for a one-off portfolio-clip edit."""
    rel_path = (payload.get("relPath") or "").strip()
    if not rel_path:
        raise ValueError("relPath가 필요합니다.")
    abs_path = os.path.normpath(os.path.join(BASE_DIR, rel_path))
    if not (abs_path + os.sep).startswith(BASE_DIR + os.sep):
        raise ValueError("허용되지 않는 경로입니다.")
    if not os.path.isfile(abs_path):
        raise ValueError("동영상 파일을 찾을 수 없습니다: %s" % rel_path)

    trim_start = payload.get("start")
    trim_end = payload.get("end")
    if trim_start is None and trim_end is None:
        raise ValueError("시작/끝 시간이 필요합니다.")

    out_dir = os.path.dirname(abs_path) or BASE_DIR
    fd, tmp_out = tempfile.mkstemp(suffix=".mp4", dir=out_dir)
    os.close(fd)
    try:
        _run_ffmpeg(abs_path, tmp_out, trim_start=trim_start, trim_end=trim_end)
        os.replace(tmp_out, abs_path)
        _extract_poster(abs_path)
    except Exception:
        try:
            os.unlink(tmp_out)
        except OSError:
            pass
        raise

    width, height = _probe_video_dims(abs_path)
    return {"relPath": rel_path, "width": width, "height": height}


def optimize_video(payload):
    """Re-encode a video (base64 dataUrl upload, or a direct video URL) to a
    web-friendly H.264/AAC mp4 with faststart. Vimeo/YouTube links never reach
    this function — those platforms already serve optimized video, so
    builder.html embeds them directly via iframe instead of routing them here.
    File uploads go through /optimize-video-raw (optimize_video_from_bytes)
    instead of this dataUrl path now; this is kept for the "link" mode and as a
    fallback."""
    mode = payload.get("mode") or "upload"
    folder = _sanitize_folder(payload.get("folder"))
    filename = (payload.get("filename") or "video").strip() or "video"

    if mode == "upload":
        data_url = payload.get("dataUrl") or ""
        if "," not in data_url:
            raise ValueError("dataUrl이 올바르지 않습니다.")
        raw = base64.b64decode(data_url.split(",", 1)[1])
        return optimize_video_from_bytes(raw, folder, filename)

    # mode == "link": a direct video URL (not Vimeo/YouTube) — ffmpeg reads it over HTTP
    url = (payload.get("url") or "").strip()
    if not url:
        raise ValueError("동영상 링크가 필요합니다.")

    name_noext = os.path.splitext(filename)[0] or "video"
    out_dir = os.path.join(BASE_DIR, folder) if folder else BASE_DIR
    os.makedirs(out_dir, exist_ok=True)
    out_name = _unique_path(out_dir, name_noext, ".mp4", suffix="-web")
    out_abs = os.path.join(out_dir, out_name)
    out_rel = (folder + "/" + out_name) if folder else out_name

    _run_ffmpeg(url, out_abs)
    width, height = _probe_video_dims(out_abs)
    return {"relPath": out_rel, "width": width, "height": height}


def run_claude(prompt, schema):
    cmd = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
        "--model", CLAUDE_MODEL,
        "--max-budget-usd", MAX_BUDGET_USD,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CLAUDE_TIMEOUT_SEC, cwd=BASE_DIR)
    if proc.returncode != 0:
        raise RuntimeError("claude CLI exited with code %s: %s" % (proc.returncode, proc.stderr[:500]))
    payload = json.loads(proc.stdout)
    if payload.get("is_error"):
        raise RuntimeError(payload.get("result", "claude CLI reported an error"))
    structured = payload.get("structured_output")
    if not structured:
        raise RuntimeError("No structured_output in claude response")
    return structured


TONE_LABELS = {
    "observer": "관찰자 — 1인칭이지만 감정을 절제한 건조체로, 현장을 지켜본 사람처럼 서술",
    "third-person": "3인칭 — 프로젝트/브랜드를 주어로 삼아 관찰 대상처럼 서술",
    "interview": "인터뷰체 — 질문에 답하듯, 실제로 누가 물어봐서 설명하는 듯한 구어에 가까운 톤",
}
STRUCTURE_LABELS = {
    "three-act": "3막 구조 — 맥락(어떤 상황이었는지) → 접근(어떻게 풀었는지) → 결과(무엇을 만들었는지) 순서로 전개",
    "vignette": "비네트 — 하나의 이어지는 서사 대신, 장면·순간 단위의 짧은 단편들을 나열하는 방식으로 전개",
    "single-flow": "단일 흐름 — 막이나 장면 구분 없이 하나의 흐름으로 처음부터 끝까지 이어서 서술",
}
PHOTO_FLOW_LABELS = {
    "match-text": "글에 맞춤 — 사진의 순서를 신경 쓰지 말고, 글의 논리적 전개에 맞춰서만 서술",
    "chronological": "시간순 — 실제 진행 순서(기획→촬영/제작→결과)를 따라가듯 서술",
    "detail-to-wide": "디테일 → 와이드 — 작은 디테일/장면에서 시작해 점점 큰 그림으로 확장하듯 서술",
    "wide-to-detail": "와이드 → 디테일 — 전체 그림을 먼저 보여준 뒤 점점 구체적인 디테일로 좁혀가듯 서술",
}


def build_direction_block(direction):
    direction = direction or {}
    tone = TONE_LABELS.get(direction.get("tone"), TONE_LABELS["observer"])
    structure = STRUCTURE_LABELS.get(direction.get("structure"), STRUCTURE_LABELS["three-act"])
    photo_flow = PHOTO_FLOW_LABELS.get(direction.get("photoFlow"), PHOTO_FLOW_LABELS["match-text"])
    length = direction.get("length", "medium")

    if length == "short":
        try:
            lines = max(1, int(direction.get("shortLines") or 3))
        except (TypeError, ValueError):
            lines = 3
        length_label = "짧게 — 전체 문단을 합쳐 총 %d줄 내외로, 군더더기 없이 압축해서" % lines
    elif length == "long":
        length_label = "길게 — 배경·과정·디테일을 충분히 풀어서, 문단을 아끼지 말고"
    else:
        length_label = "중간 — 배경과 결과를 핵심만 짚어서, 너무 짧지도 길지도 않게"

    note = (direction.get("note") or "").strip()
    note_line = ("- 이번 글에서 특별히 강조할 것: %s\n" % note) if note else ""

    return (
        "\n\n## 이번 생성 방향 설정 (아래 조건을 모두 지켜서 써라)\n"
        "- 어투: %s\n"
        "- 구조: %s\n"
        "- 길이: %s\n"
        "- 사진 흐름: %s\n"
        "%s"
    ) % (tone, structure, length_label, photo_flow, note_line)


def build_prompt(title, tag, meta, direction=None, mode="new", draft="", section=""):
    voice = load_voice_rulebook()
    examples, examples_source = load_voice_examples()

    voice_block = ""
    if voice:
        voice_block = (
            "\n\n## 문체 규칙 (반드시 지킬 것)\n"
            "아래는 내 실제 글에서 관찰한 문체 규칙이다. 이 규칙을 예외 없이 따라서 써라:\n\n"
            + voice + "\n"
        )
    examples_block = ""
    if examples:
        examples_block = (
            "\n\n## 문체 예시 (출처: %s — 표현을 그대로 베끼지 말고 톤·구조만 따라할 것)\n\n%s\n"
            % (examples_source, examples)
        )
    section = (section or "").strip()
    section_line = (
        "\n- 이 글이 들어갈 섹션/블록: \"%s\" — 프로젝트 전체 소개가 아니라 이 섹션 하나에만 해당하는 내용으로 작성해 (다른 섹션과 내용이 겹치지 않게)"
        % section
    ) if section else ""

    if mode == "polish":
        return (
            "너는 광고 에이전시 아트디렉터 본인이야. 아래는 네가 포트폴리오 사이트에 올릴 프로젝트 소개글로 쓰려고 "
            "직접 쓴 초안이야:\n\n---\n" + draft + "\n---\n"
            + voice_block + examples_block +
            "\n\n위 문체 규칙과 예시의 톤·리듬을 참고해서, 이 초안의 내용과 의미는 그대로 유지한 채 문장만 학습된 문체로 다듬어줘. "
            "새로운 사실이나 에피소드를 지어내지 마." + section_line + "\n\n"
            "다음 필드를 JSON으로 반환해:\n"
            "- title: \"%s\" (그대로 유지, 빈 문자열이면 빈 문자열)\n"
            "- tag: \"%s\" (그대로 유지, 빈 문자열이면 빈 문자열)\n"
            "- meta: \"%s\" (그대로 유지, 빈 문자열이면 빈 문자열)\n"
            "- heading: 초안에 슬로건/제목으로 보이는 부분이 있으면 다듬어서, 없으면 빈 문자열\n"
            "- paragraphs: 초안을 다듬은 문단들의 배열 (초안의 문단 구성과 순서를 최대한 존중)"
        ) % (title or "", tag or "", meta or "")

    context_bits = []
    if title:
        context_bits.append('현재 프로젝트명: "%s"' % title)
    if tag:
        context_bits.append('현재 카테고리: "%s"' % tag)
    if meta:
        context_bits.append('현재 클라이언트/에이전시: "%s"' % meta)
    context = "\n".join(context_bits) if context_bits else "(아직 입력된 내용 없음)"

    direction_block = build_direction_block(direction)

    if section:
        return (
            "너는 광고 에이전시 아트디렉터 본인이 되어, 자기 포트폴리오 사이트에 들어갈 프로젝트 소개 초안을 직접 쓰는 사람이야.\n"
            "아래는 지금까지 입력된 정보야:\n" + context + "\n"
            + voice_block + examples_block + direction_block + section_line +
            "\n\n위 문체 규칙과 예시 톤, 그리고 이번 생성 방향 설정을 모두 따라서, 이 섹션에 들어갈 문단을 한국어로 작성해줘. "
            "실존하는 특정 인물이나 사건을 사실인 것처럼 단정하지 말고, 포트폴리오 초안(플레이스홀더)이라는 톤을 유지해줘.\n"
            "다음 필드를 JSON으로 반환해:\n"
            "- title: \"%s\" (그대로 유지, 빈 문자열이면 빈 문자열)\n"
            "- tag: \"%s\" (그대로 유지, 빈 문자열이면 빈 문자열)\n"
            "- meta: \"%s\" (그대로 유지, 빈 문자열이면 빈 문자열)\n"
            "- heading: 이 섹션의 소제목/슬로건 한 줄\n"
            "- paragraphs: 이 섹션 내용을 설명하는 한국어 문단 (배열)"
        ) % (title or "", tag or "", meta or "")

    return (
        "너는 광고 에이전시 아트디렉터 본인이 되어, 자기 포트폴리오 사이트에 들어갈 프로젝트 소개 초안을 직접 쓰는 사람이야.\n"
        "아래는 지금까지 입력된 정보야:\n" + context + "\n"
        + voice_block + examples_block + direction_block +
        "\n\n위 문체 규칙과 예시 톤, 그리고 이번 생성 방향 설정을 모두 따라서, 이 프로젝트에 대한 그럴듯한 캠페인 케이스 스터디 초안을 한국어로 작성해줘. "
        "실존하는 특정 인물이나 사건을 사실인 것처럼 단정하지 말고, 포트폴리오 초안(플레이스홀더)이라는 톤을 유지해줘.\n"
        "다음 필드를 JSON으로 반환해:\n"
        "- title: 프로젝트명 (기존 값이 이미 괜찮으면 그대로 유지)\n"
        "- tag: 짧은 카테고리 (예: Brand Campaign, Digital Campaign)\n"
        "- meta: \"Client — ○○○ · Agency — ○○○\" 형식의 한 줄\n"
        "- heading: 캠페인 슬로건 한 줄\n"
        "- paragraphs: 캠페인 배경·컨셉·실행을 설명하는 한국어 문단 2~3개 (배열)"
    )


def build_info_generate_prompt(mode, lead, paragraphs, draft, note):
    """`mode` is 'new' (write the INFO page bio from scratch) or 'polish'
    (rewrite a draft the user already wrote, in the learned voice, without
    inventing new content)."""
    voice = load_voice_rulebook()
    examples, examples_source = load_voice_examples()

    voice_block = ""
    if voice:
        voice_block = (
            "\n\n## 문체 규칙 (반드시 지킬 것)\n"
            "아래는 내 실제 글에서 관찰한 문체 규칙이다. 이 규칙을 예외 없이 따라서 써라:\n\n"
            + voice + "\n"
        )
    examples_block = ""
    if examples:
        examples_block = (
            "\n\n## 문체 예시 (출처: %s — 표현을 그대로 베끼지 말고 톤·리듬만 따라할 것)\n\n%s\n"
            % (examples_source, examples)
        )

    note = (note or "").strip()
    note_line = ("\n- 이번에 특별히 반영할 것: %s" % note) if note else ""

    if mode == "polish":
        return (
            "너는 광고 에이전시 아트디렉터 본인이야. 아래는 네가 포트폴리오 사이트 INFO 페이지(자기소개)에 쓰려고 "
            "직접 쓴 초안이야:\n\n---\n" + draft + "\n---\n"
            + voice_block + examples_block +
            "\n\n위 문체 규칙과 예시의 톤·리듬을 참고해서, 이 초안의 내용과 의미는 그대로 유지한 채 문장만 다듬어줘. "
            "새로운 사실이나 내용을 지어내지 말고, 표현과 리듬만 손봐." + note_line + "\n\n"
            "다음 필드를 JSON으로 반환해:\n"
            "- lead: 도입부로 쓸 인사말 1~2줄 (초안에 도입부가 있으면 그것을 다듬어서, 없으면 초안 중 도입에 어울리는 부분으로)\n"
            "- paragraphs: 나머지 내용을 다듬은 문단들의 배열 (초안의 문단 구성을 최대한 존중, 순서 유지)"
        )

    context = ""
    if lead or paragraphs:
        context = (
            "\n\n## 참고 — 지금까지 써둔 내용 (톤 참고용일 뿐, 그대로 베끼지 말고 새로 써)\n인사말: %s\n본문: %s\n"
            % (lead or "(없음)", "\n".join(paragraphs) if paragraphs else "(없음)")
        )

    return (
        "너는 광고 에이전시 아트디렉터 본인이야. 자기 포트폴리오 사이트의 INFO 페이지(자기소개)에 들어갈 "
        "인사말과 짧은 자기소개 글을 새로 써줘."
        + context + voice_block + examples_block + note_line +
        "\n\n다음 필드를 JSON으로 반환해:\n"
        "- lead: 도입부로 쓸 인사말 1~2줄\n"
        "- paragraphs: 이어지는 자기소개 문단들의 배열 (3~5개, 너무 길지 않게)"
    )


def build_translate_prompt(direction, data):
    src_lang = "한국어" if direction == "ko-en" else "영어"
    dst_lang = "영어" if direction == "ko-en" else "한국어"
    return (
        "아래는 광고 에이전시 아트디렉터 포트폴리오 사이트의 프로젝트 텍스트(JSON)야. "
        "%s로 되어 있는 텍스트를 자연스러운 %s로 번역해줘. "
        "고유명사(브랜드명, 사람 이름)는 그대로 두고, 나머지는 포트폴리오/케이스 스터디 톤을 유지해서 번역해.\n"
        "번역할 원본 JSON:\n%s\n\n"
        "동일한 필드 구조(title, tag, meta, blocks[].label, blocks[].heading, blocks[].paragraphs)로 번역 결과를 JSON으로 반환해줘. "
        "blocks[].label은 섹션 제목(예: \"Key Visual\")이니 짧고 간결하게 옮겨줘. "
        "빈 문자열이나 빈 배열은 그대로 빈 값으로 둬."
    ) % (src_lang, dst_lang, json.dumps(data, ensure_ascii=False))


def build_info_translate_prompt(direction, data):
    src_lang = "한국어" if direction == "ko-en" else "영어"
    dst_lang = "영어" if direction == "ko-en" else "한국어"
    return (
        "아래는 광고 에이전시 아트디렉터 포트폴리오 사이트의 INFO(자기소개) 페이지 텍스트(JSON)야. "
        "%s로 되어 있는 텍스트를 자연스러운 %s로 번역해줘. "
        "고유명사(이름, 브랜드명)는 그대로 두고, 원문의 줄바꿈(\\n) 위치는 최대한 자연스럽게 유지해줘.\n"
        "번역할 원본 JSON:\n%s\n\n"
        "lead 1개와 paragraphs 배열(원본과 정확히 같은 개수)로 이루어진 동일한 필드 구조(lead, paragraphs)로 "
        "번역 결과를 JSON으로 반환해줘. 빈 문자열은 그대로 빈 값으로 둬."
    ) % (src_lang, dst_lang, json.dumps(data, ensure_ascii=False))


class JSSyntaxError(Exception):
    pass


def _skip_string_or_comment(text, i, n):
    """If text[i] starts a //, /* */ comment or a quoted string, return the index
    right after it. Otherwise return None."""
    c = text[i]
    if c == "/" and i + 1 < n and text[i + 1] == "/":
        j = text.find("\n", i)
        return n if j == -1 else j
    if c == "/" and i + 1 < n and text[i + 1] == "*":
        j = text.find("*/", i + 2)
        return n if j == -1 else j + 2
    if c in ("'", '"', "`"):
        quote = c
        j = i + 1
        while j < n:
            if text[j] == "\\":
                j += 2
                continue
            if text[j] == quote:
                return j + 1
            j += 1
        return n
    return None


def _find_matching_bracket(text, open_idx):
    """Given the index of an opening '{' or '[', return the index of its matching
    closer, skipping over string/template literals and comments."""
    n = len(text)
    depth = 0
    i = open_idx
    while i < n:
        skip_to = _skip_string_or_comment(text, i, n)
        if skip_to is not None:
            i = skip_to
            continue
        c = text[i]
        if c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise JSSyntaxError("unbalanced brackets starting at %d" % open_idx)


def _split_top_level_items(text, start, end):
    """Return (start, end) spans for each top-level {...} object literal found
    between text[start:end] (i.e. inside a JS array), ignoring comments."""
    items = []
    i = start
    item_start = None
    item_content_end = None
    depth = 0
    while i < end:
        skip_to = _skip_string_or_comment(text, i, end)
        if skip_to is not None:
            i = skip_to
            continue
        c = text[i]
        if c in "{[":
            if depth == 0 and item_start is None:
                item_start = i
            depth += 1
            i += 1
            continue
        if c in "}]":
            depth -= 1
            i += 1
            if depth == 0 and item_start is not None:
                item_content_end = i
            continue
        if c == "," and depth == 0:
            if item_start is not None:
                items.append((item_start, item_content_end if item_content_end is not None else i))
                item_start = None
                item_content_end = None
            i += 1
            continue
        i += 1
    if item_start is not None:
        items.append((item_start, item_content_end if item_content_end is not None else end))
    return items


def _reindent_for_replace(code, base="    "):
    """First line keeps no extra indent (the surrounding HTML already supplies
    the column it sits at); every other line gets `base` prepended."""
    lines = code.strip("\n").split("\n")
    out = [lines[0]]
    for ln in lines[1:]:
        out.append(base + ln if ln.strip() else ln)
    return "\n".join(out)


def _reindent_for_insert(code, base="    "):
    lines = code.strip("\n").split("\n")
    return "\n".join(base + ln if ln.strip() else ln for ln in lines)


def publish_project(project_id, code):
    """Insert or replace `project_id`'s object literal inside index.html's
    `const PROJECTS = [...]` array with `code` (a JS object literal string, as
    produced by builder.html's exportProjectCode)."""
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    marker = "const PROJECTS = ["
    marker_idx = html.find(marker)
    if marker_idx == -1:
        raise RuntimeError("index.html에서 'const PROJECTS = [' 를 찾을 수 없습니다.")
    open_idx = marker_idx + len(marker) - 1
    close_idx = _find_matching_bracket(html, open_idx)

    items = _split_top_level_items(html, open_idx + 1, close_idx)

    id_re = re.compile(r'id\s*:\s*"((?:[^"\\]|\\.)*)"')
    target = None
    for (s, e) in items:
        m = id_re.search(html, s, e)
        if m and m.group(1) == project_id:
            target = (s, e)
            break

    if target:
        s, e = target
        new_html = html[:s] + _reindent_for_replace(code) + html[e:]
        action = "updated"
    else:
        indented = _reindent_for_insert(code)
        if items:
            insert_at = items[-1][1]
            new_html = html[:insert_at] + ",\n" + indented + html[insert_at:]
        else:
            insert_at = open_idx + 1
            new_html = html[:insert_at] + "\n" + indented + "\n  " + html[insert_at:]
        action = "added"

    with open(INDEX_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)
    return action


# Every trailing whitespace-consuming group below uses [ \t]* rather than \s* —
# \s* would also swallow the newline that separates this field from the next
# one, so replacing the match would jam the next field onto the same line
# (e.g. "order:3,color:..." instead of "order:3,\n      color:...").
_ORDER_FIELD_RE = re.compile(r"order\s*:\s*-?\d+(?:\.\d+)?\s*,?[ \t]*")
_HIDDEN_FIELD_RE = re.compile(r"hidden\s*:\s*(?:true|false)\s*,?[ \t]*(?:/\*.*?\*/[ \t]*)?", re.S)
# used only to fully DELETE the field (hidden -> false): also eats the leading
# newline+indent so removing it doesn't leave a blank line behind.
_HIDDEN_FIELD_REMOVE_RE = re.compile(r"\n?[ \t]*hidden\s*:\s*(?:true|false)\s*,?[ \t]*(?:/\*.*?\*/[ \t]*)?", re.S)
_CATEGORY_FIELD_RE = re.compile(r'category\s*:\s*"[^"]*"\s*,')
_ID_FIELD_RE = re.compile(r'id\s*:\s*"((?:[^"\\]|\\.)*)"')


def _set_simple_field(segment, id_m, field_re, new_stmt):
    """Replace `field_re`'s match in-place, or insert `new_stmt` right after
    category:"...", (or after id:"...", as a fallback) if the field is missing."""
    m = field_re.search(segment)
    if m:
        return segment[:m.start()] + new_stmt + segment[m.end():]
    cat_m = _CATEGORY_FIELD_RE.search(segment)
    insert_at = cat_m.end() if cat_m else id_m.end() + 1
    return segment[:insert_at] + "\n      " + new_stmt + segment[insert_at:]


def publish_order(items):
    """Update just the `order:`/`hidden:` fields of each listed project (by id)
    inside index.html's `const PROJECTS = [...]` array, leaving every other
    field of that project untouched. Backs builder.html's "순서를 사이트에 반영"
    button, which lets a sidebar reorder or hide/show toggle reach the live
    Work/Play list without republishing each affected project's full data.

    `items` is a list of {"id", "order", "hidden"} dicts ("hidden" optional —
    only sent for projects where it's actually true, so omitted/False both
    mean "make sure it's visible"). Returns how many matching projects were
    actually updated."""
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    marker = "const PROJECTS = ["
    marker_idx = html.find(marker)
    if marker_idx == -1:
        raise RuntimeError("index.html에서 'const PROJECTS = [' 를 찾을 수 없습니다.")
    open_idx = marker_idx + len(marker) - 1
    close_idx = _find_matching_bracket(html, open_idx)

    entries = _split_top_level_items(html, open_idx + 1, close_idx)
    by_id = {it.get("id"): it for it in items if isinstance(it, dict) and it.get("id") is not None}

    updated_count = 0
    pieces = []
    cursor = open_idx + 1
    for (s, e) in entries:
        pieces.append(html[cursor:s])
        segment = html[s:e]
        id_m = _ID_FIELD_RE.search(segment)
        pid = id_m.group(1) if id_m else None
        it = by_id.get(pid) if pid is not None else None
        if it is not None:
            if it.get("order") is not None:
                segment = _set_simple_field(segment, id_m, _ORDER_FIELD_RE, "order:%s," % it["order"])
            if it.get("hidden"):
                segment = _set_simple_field(segment, id_m, _HIDDEN_FIELD_RE, "hidden:true,")
            else:
                segment = _HIDDEN_FIELD_REMOVE_RE.sub("", segment, count=1)
            updated_count += 1
        pieces.append(segment)
        cursor = e
    pieces.append(html[cursor:close_idx])

    new_html = html[:open_idx + 1] + "".join(pieces) + html[close_idx:]
    with open(INDEX_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)
    return updated_count


def _find_matching_div_close(text, start_idx):
    """`start_idx` is right after the opening <div ...> tag's closing '>'.
    Returns the index of the matching '</div>' tag's start, counting nested
    <div> opens/closes in between."""
    depth = 1
    tag_re = re.compile(r"<div\b|</div\s*>")
    for m in tag_re.finditer(text, start_idx):
        if m.group(0).startswith("<div"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return m.start()
    raise RuntimeError("matching </div>를 찾을 수 없습니다.")


def _info_text_to_html(text):
    return html_lib.escape(text or "", quote=False).replace("\n", "<br>")


INFO_PARA_FONT_VARS = {"thin": "var(--font-thin)", "medium": "var(--font-medium)", "bold": "var(--font-bold)"}
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _valid_hex_color(c):
    return c if isinstance(c, str) and _HEX_COLOR_RE.match(c) else None


def _info_style_attr(obj, base_clamp, prefix=""):
    """Mirrors builder.html's infoParagraphStyleAttr()/infoLeadStyleAttr() — same 5
    fields (font family/weight/size/letter-spacing/color), read either off a paragraph
    dict directly (prefix="") or off the top-level INFO record's lead* fields
    (prefix="lead"). `base_clamp` is the CSS clamp() the paragraph type or the lead
    normally renders at, since the size slider is a multiplier on top of that."""
    styles = []
    font_family = obj.get(prefix + "FontFamily" if prefix else "fontFamily")
    if font_family in INFO_PARA_FONT_VARS:
        styles.append("font-family:%s" % INFO_PARA_FONT_VARS[font_family])
    font_weight = obj.get(prefix + "FontWeight" if prefix else "fontWeight")
    if font_weight:
        try:
            styles.append("font-weight:%d" % int(font_weight))
        except (TypeError, ValueError):
            pass
    font_scale = obj.get(prefix + "FontScale" if prefix else "fontScale")
    if font_scale not in (None, "", 1, 1.0):
        try:
            scale = float(font_scale)
            if abs(scale - 1.0) > 0.001:
                styles.append("font-size:calc(%s * %s)" % (base_clamp, scale))
        except (TypeError, ValueError):
            pass
    letter_spacing = obj.get(prefix + "LetterSpacing" if prefix else "letterSpacing")
    if letter_spacing:
        try:
            styles.append("letter-spacing:%sem" % float(letter_spacing))
        except (TypeError, ValueError):
            pass
    color = _valid_hex_color(obj.get(prefix + "Color" if prefix else "color"))
    if color:
        styles.append("color:%s" % color)
    return (' style="%s"' % ";".join(styles)) if styles else ""


def _info_paragraph_style_attr(p):
    return _info_style_attr(p, "clamp(1rem, 1.7vw, 1.2rem)")


def _info_lead_style_attr(data):
    return _info_style_attr(data, "clamp(1.4rem, 3.2vw, 2.3rem)", prefix="lead")


def render_info_content_html(data):
    """Render builder.html's INFO edit form data back into the exact markup
    shape index.html's #info-view expects (see its `.info-content` block)."""
    lead = data.get("lead") or ""
    paragraphs = data.get("paragraphs") or []
    links = data.get("links") or []

    parts = ['<p class="info-lead"%s>%s</p>' % (_info_lead_style_attr(data), _info_text_to_html(lead))]
    for p in paragraphs:
        text = (p.get("text") or "").strip()
        if not text:
            continue
        ptype = "tagline" if p.get("type") == "tagline" else "body"
        parts.append(
            '<p class="info-%s"%s>%s</p>' % (ptype, _info_paragraph_style_attr(p), _info_text_to_html(text))
        )

    link_parts = []
    for l in links:
        label = (l.get("label") or "").strip()
        url = (l.get("url") or "").strip()
        if not label or not url:
            continue
        target = ' target="_blank" rel="noopener"' if url.startswith("http") else ""
        link_parts.append(
            '<a href="%s"%s>%s</a>' % (html_lib.escape(url, quote=True), target, html_lib.escape(label, quote=False))
        )
    parts.append('<div class="links">\n          ' + "\n          ".join(link_parts) + "\n        </div>")

    return "\n\n        ".join(parts)


def publish_info(data):
    """Replace the contents of index.html's `<div class="info-content">...
    </div>` block (the INFO page overlay's text) with builder.html's INFO
    edit form data."""
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    marker = '<div class="info-content">'
    marker_idx = content.find(marker)
    if marker_idx == -1:
        raise RuntimeError('index.html에서 \'<div class="info-content">\'를 찾을 수 없습니다.')
    inner_start = marker_idx + len(marker)
    close_idx = _find_matching_div_close(content, inner_start)

    rendered = render_info_content_html(data)
    new_content = content[:inner_start] + "\n        " + rendered + "\n      " + content[close_idx:]

    with open(INDEX_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)


INFO_BG_PATH = os.path.join(BASE_DIR, "info-bg.jpg")
INFO_BG_MOBILE_PATH = os.path.join(BASE_DIR, "info-bg-mobile.jpg")


def save_info_bg_image(payload):
    """Overwrite info-bg.jpg (PC) or info-bg-mobile.jpg (mobile) on disk with a newly
    attached photo, depending on payload["target"]. Always saved under that exact same
    filename (re-encoded to JPEG regardless of the source format) so index.html's
    `url("info-bg.jpg")`/`url("info-bg-mobile.jpg")` CSS references never have to
    change — the file just rides along with whatever git commit the next Publish makes."""
    data_url = payload.get("dataUrl") or ""
    if "," not in data_url:
        raise ValueError("dataUrl이 올바르지 않습니다.")
    target = payload.get("target") or "pc"
    out_path = INFO_BG_MOBILE_PATH if target == "mobile" else INFO_BG_PATH
    raw = base64.b64decode(data_url.split(",", 1)[1])
    img = Image.open(io.BytesIO(raw))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.save(out_path, quality=100)
    return {"ok": True, "target": target}


def save_project_image(payload):
    """Write an uploaded photo (hero image, or a block photo added via the plain
    file picker/drag-drop — see /upload-project-image) into a project's asset
    folder on disk, returning the relPath it was saved under. A plain <input
    type=file> or drag-drop gives the browser no folder information at all —
    unlike the folder picker, whose webkitRelativePath tells us exactly where the
    file already lives on disk — so without this round trip the picked photo's
    relPath would default to a bare filename that 404s once published, even if
    the file happens to already exist on disk somewhere. This guarantees the file
    actually exists at the relPath recorded. Also doubles as the "web 최적화"
    step for stills (mirrors optimize_video's ffmpeg resize for video): every
    upload gets capped to MAX_IMAGE_DIM on its long edge before being saved."""
    data_url = payload.get("dataUrl") or ""
    if "," not in data_url:
        raise ValueError("dataUrl이 올바르지 않습니다.")
    raw = base64.b64decode(data_url.split(",", 1)[1])
    img = Image.open(io.BytesIO(raw))
    folder = _sanitize_folder(payload.get("folder"))
    base_name = (payload.get("filename") or "image.jpg").strip() or "image.jpg"
    name_noext, ext = os.path.splitext(base_name)
    if not ext:
        ext = ".jpg"

    out_dir = os.path.join(BASE_DIR, folder) if folder else BASE_DIR
    os.makedirs(out_dir, exist_ok=True)
    out_name = _unique_plain_path(out_dir, name_noext, ext)
    out_abs = os.path.join(out_dir, out_name)
    out_rel = (folder + "/" + out_name) if folder else out_name

    if img.format == "GIF" and getattr(img, "is_animated", False):
        frames = []
        durations = []
        for frame in ImageSequence.Iterator(img):
            frames.append(frame.convert("RGBA"))
            durations.append(frame.info.get("duration", 100))
        frames = _resize_cap_frames(frames)
        frames[0].save(
            out_abs, save_all=True, append_images=frames[1:],
            loop=img.info.get("loop", 0), duration=durations, disposal=2,
        )
        out_w, out_h = frames[0].size
    else:
        img = _resize_cap(img)
        save_kwargs = {}
        if ext.lower() in (".jpg", ".jpeg"):
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            save_kwargs["quality"] = 100
        elif ext.lower() == ".webp":
            save_kwargs["quality"] = 100
        elif ext.lower() == ".png":
            save_kwargs["optimize"] = True
        img.save(out_abs, **save_kwargs)
        out_w, out_h = img.size

    return {"relPath": out_rel, "width": out_w, "height": out_h}


def _run_git(args):
    return subprocess.run(["git"] + args, cwd=BASE_DIR, capture_output=True, text=True)


def git_commit_and_push(title):
    check = _run_git(["rev-parse", "--is-inside-work-tree"])
    if check.returncode != 0:
        raise RuntimeError("아직 git 저장소가 아닙니다. 먼저 GitHub 연동을 완료해주세요.")
    add = _run_git(["add", "-A"])
    if add.returncode != 0:
        raise RuntimeError(add.stderr[:800])
    status = _run_git(["status", "--porcelain"])
    if not status.stdout.strip():
        return {"committed": False, "pushed": False, "note": "변경사항이 없습니다 (이미 최신 상태)."}
    commit = _run_git(["commit", "-m", "Publish: %s" % title])
    if commit.returncode != 0:
        raise RuntimeError(commit.stderr[:800])
    push = _run_git(["push"])
    if push.returncode != 0:
        raise RuntimeError(
            "커밋은 완료됐지만 push에 실패했습니다: %s" % push.stderr[:800]
        )
    return {
        "committed": True,
        "pushed": True,
        "note": "GitHub에 푸시 완료 — Vercel이 자동으로 재배포합니다 (약 1분 소요).",
    }


class Handler(http.server.BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/scan-images":
            qs = urllib.parse.parse_qs(parsed.query)
            name = (qs.get("folder") or [""])[0]
            folder = find_project_folder(name)
            if not folder:
                self._send_json(200, {"folder": None, "images": []})
                return
            self._send_json(200, {"folder": folder, "images": list_images(folder)})
            return
        if parsed.path == "/scan-videos":
            qs = urllib.parse.parse_qs(parsed.query)
            name = (qs.get("folder") or [""])[0]
            folder = find_project_folder(name)
            if not folder:
                self._send_json(200, {"folder": None, "videos": []})
                return
            # Only list videos that already went through our ffmpeg web-optimize pipeline
            # (recognized by the "-web"/"-web2"/... suffix _unique_path always appends) —
            # the builder's "폴더에서 선택" picker must never surface a raw, un-optimized
            # video that happens to be sitting in the project folder for some other reason.
            optimized = [v for v in list_videos(folder) if re.search(r"-web\d*$", os.path.splitext(v)[0], re.IGNORECASE)]
            self._send_json(200, {"folder": folder, "videos": optimized})
            return
        if parsed.path == "/ping":
            self._send_json(200, {"ok": True})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/optimize-video-raw":
            # Raw binary body (the video file itself, streamed straight off the socket) —
            # never JSON-decoded, so large uploads never get held in memory as one giant
            # base64 string (that's what was crashing the tab on big vertical/phone videos).
            qs = urllib.parse.parse_qs(parsed.query)
            folder = (qs.get("folder") or [""])[0]
            filename = (qs.get("filename") or ["video"])[0]
            trim_start_raw = (qs.get("trimStart") or [None])[0]
            trim_end_raw = (qs.get("trimEnd") or [None])[0]
            try:
                trim_start = float(trim_start_raw) if trim_start_raw not in (None, "") else None
                trim_end = float(trim_end_raw) if trim_end_raw not in (None, "") else None
            except ValueError:
                self._send_json(400, {"error": "trimStart/trimEnd는 숫자(초)여야 합니다."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b""
            except Exception as e:
                self._send_json(400, {"error": "bad request: %s" % e})
                return
            if not raw:
                self._send_json(400, {"error": "동영상 데이터가 비어 있습니다."})
                return
            try:
                result = optimize_video_from_bytes(raw, folder, filename, trim_start=trim_start, trim_end=trim_end)
            except ValueError as e:
                self._send_json(400, {"error": str(e)})
                return
            except Exception as e:
                self._send_json(500, {"error": "동영상 최적화 실패: %s" % e})
                return
            self._send_json(200, dict({"ok": True}, **result))
            return

        if parsed.path not in ("/generate", "/generate-info", "/translate", "/translate-info", "/publish", "/publish-info", "/publish-order", "/upload-info-bg", "/upload-project-image", "/crop", "/optimize-video", "/trim-video-existing"):
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw or b"{}")
        except Exception as e:
            self._send_json(400, {"error": "bad request: %s" % e})
            return

        if parsed.path == "/crop":
            try:
                result = crop_image(payload)
            except ValueError as e:
                self._send_json(400, {"error": str(e)})
                return
            except Exception as e:
                self._send_json(500, {"error": "크롭 실패: %s" % e})
                return
            self._send_json(200, dict({"ok": True}, **result))
            return

        if parsed.path == "/optimize-video":
            try:
                result = optimize_video(payload)
            except ValueError as e:
                self._send_json(400, {"error": str(e)})
                return
            except Exception as e:
                self._send_json(500, {"error": "동영상 최적화 실패: %s" % e})
                return
            self._send_json(200, dict({"ok": True}, **result))
            return

        if parsed.path == "/trim-video-existing":
            try:
                result = trim_video_existing(payload)
            except ValueError as e:
                self._send_json(400, {"error": str(e)})
                return
            except Exception as e:
                self._send_json(500, {"error": "동영상 다듬기 실패: %s" % e})
                return
            self._send_json(200, dict({"ok": True}, **result))
            return

        if parsed.path == "/publish":
            project_id = (payload.get("id") or "").strip()
            code = payload.get("code") or ""
            title = (payload.get("title") or project_id).strip()
            if not project_id or not code.strip():
                self._send_json(400, {"error": "id와 code가 필요합니다."})
                return
            try:
                action = publish_project(project_id, code)
            except Exception as e:
                self._send_json(500, {"error": "index.html 업데이트 실패: %s" % e})
                return
            try:
                git_result = git_commit_and_push(title)
            except Exception as e:
                self._send_json(500, {
                    "error": "%s (index.html은 이미 수정되었습니다 — 직접 git commit/push 하거나, 문제를 해결한 뒤 다시 Publish 하세요.)" % e
                })
                return
            result = {"action": action}
            result.update(git_result)
            self._send_json(200, result)
            return

        if parsed.path == "/publish-info":
            try:
                publish_info(payload)
            except Exception as e:
                self._send_json(500, {"error": "index.html 업데이트 실패: %s" % e})
                return
            try:
                git_result = git_commit_and_push("Info page")
            except Exception as e:
                self._send_json(500, {
                    "error": "%s (index.html은 이미 수정되었습니다 — 직접 git commit/push 하거나, 문제를 해결한 뒤 다시 Publish 하세요.)" % e
                })
                return
            result = {"action": "updated"}
            result.update(git_result)
            self._send_json(200, result)
            return

        if parsed.path == "/publish-order":
            items = payload.get("items") if isinstance(payload.get("items"), list) else []
            if not items:
                self._send_json(400, {"error": "items가 필요합니다."})
                return
            try:
                updated = publish_order(items)
            except Exception as e:
                self._send_json(500, {"error": "index.html 업데이트 실패: %s" % e})
                return
            try:
                git_result = git_commit_and_push("Sync project order")
            except Exception as e:
                self._send_json(500, {
                    "error": "%s (index.html은 이미 수정되었습니다 — 직접 git commit/push 하거나, 문제를 해결한 뒤 다시 시도하세요.)" % e
                })
                return
            result = {"updated": updated}
            result.update(git_result)
            self._send_json(200, result)
            return

        if parsed.path == "/upload-info-bg":
            try:
                result = save_info_bg_image(payload)
            except ValueError as e:
                self._send_json(400, {"error": str(e)})
                return
            except Exception as e:
                self._send_json(500, {"error": "배경 사진 저장 실패: %s" % e})
                return
            self._send_json(200, result)
            return

        if parsed.path == "/upload-project-image":
            try:
                result = save_project_image(payload)
            except ValueError as e:
                self._send_json(400, {"error": str(e)})
                return
            except Exception as e:
                self._send_json(500, {"error": "이미지 저장 실패: %s" % e})
                return
            self._send_json(200, dict({"ok": True}, **result))
            return

        if parsed.path == "/generate":
            title = (payload.get("title") or "").strip()
            tag = (payload.get("tag") or "").strip()
            meta = (payload.get("meta") or "").strip()
            direction = payload.get("direction") if isinstance(payload.get("direction"), dict) else None
            mode = payload.get("mode") if payload.get("mode") in ("new", "polish") else "new"
            draft = (payload.get("draft") or "").strip()
            section = (payload.get("section") or "").strip()
            if mode == "polish" and not draft:
                self._send_json(400, {"error": "다듬을 글을 입력해주세요."})
                return
            try:
                prompt = build_prompt(title, tag, meta, direction, mode, draft, section)
                structured = run_claude(prompt, GENERATE_SCHEMA)
            except subprocess.TimeoutExpired:
                self._send_json(504, {"error": "claude CLI timed out"})
                return
            except Exception as e:
                self._send_json(500, {"error": str(e)})
                return

            folder = find_project_folder(structured.get("title") or title)
            images = list_images(folder) if folder else []
            structured["images"] = images
            structured["imageFolder"] = folder
            self._send_json(200, structured)
            return

        if parsed.path == "/generate-info":
            mode = payload.get("mode") if payload.get("mode") in ("new", "polish") else "new"
            lead = payload.get("lead") or ""
            paragraphs = payload.get("paragraphs") if isinstance(payload.get("paragraphs"), list) else []
            draft = (payload.get("draft") or "").strip()
            note = payload.get("note") or ""
            if mode == "polish" and not draft:
                self._send_json(400, {"error": "다듬을 글을 입력해주세요."})
                return
            try:
                prompt = build_info_generate_prompt(mode, lead, paragraphs, draft, note)
                structured = run_claude(prompt, INFO_GENERATE_SCHEMA)
            except subprocess.TimeoutExpired:
                self._send_json(504, {"error": "claude CLI timed out"})
                return
            except Exception as e:
                self._send_json(500, {"error": str(e)})
                return
            self._send_json(200, structured)
            return

        if parsed.path == "/translate-info":
            direction = payload.get("direction")
            if direction not in ("ko-en", "en-ko"):
                self._send_json(400, {"error": "direction must be 'ko-en' or 'en-ko'"})
                return
            data = {
                "lead": payload.get("lead") or "",
                "paragraphs": payload.get("paragraphs") if isinstance(payload.get("paragraphs"), list) else []
            }
            try:
                prompt = build_info_translate_prompt(direction, data)
                structured = run_claude(prompt, INFO_TRANSLATE_SCHEMA)
            except subprocess.TimeoutExpired:
                self._send_json(504, {"error": "claude CLI timed out"})
                return
            except Exception as e:
                self._send_json(500, {"error": str(e)})
                return
            self._send_json(200, structured)
            return

        # /translate
        direction = payload.get("direction")
        if direction not in ("ko-en", "en-ko"):
            self._send_json(400, {"error": "direction must be 'ko-en' or 'en-ko'"})
            return
        data = {
            "title": payload.get("title") or "",
            "tag": payload.get("tag") or "",
            "meta": payload.get("meta") or "",
            "blocks": payload.get("blocks") or []
        }
        try:
            prompt = build_translate_prompt(direction, data)
            structured = run_claude(prompt, TRANSLATE_SCHEMA)
        except subprocess.TimeoutExpired:
            self._send_json(504, {"error": "claude CLI timed out"})
            return
        except Exception as e:
            self._send_json(500, {"error": str(e)})
            return
        self._send_json(200, structured)

    def log_message(self, fmt, *args):
        print("[server] " + (fmt % args))


if __name__ == "__main__":
    print("Portfolio Builder helper server")
    print("Serving on http://localhost:%d (base dir: %s)" % (PORT, BASE_DIR))
    print("Leave this running, then click \"Generate\" inside builder.html.")
    http.server.HTTPServer(("localhost", PORT), Handler).serve_forever()
