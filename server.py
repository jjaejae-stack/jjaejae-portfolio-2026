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
import http.server
import json
import os
import re
import subprocess
import urllib.parse

PORT = 8420
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_TIMEOUT_SEC = 90
MAX_BUDGET_USD = "0.50"

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
                    "heading": {"type": "string"},
                    "paragraphs": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["heading", "paragraphs"]
            }
        }
    },
    "required": ["title", "tag", "meta", "blocks"]
}


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def find_project_folder(name):
    """Best-effort: look for a subfolder of BASE_DIR matching the project name."""
    if not name:
        return None
    candidates = [name, name.strip(), name.upper(), name.replace(" ", "")]
    try:
        entries = [e for e in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, e))]
    except OSError:
        return None
    for c in candidates:
        if c in entries:
            return c
    lowered = name.lower()
    for e in entries:
        if e.lower() == lowered:
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


def build_prompt(title, tag, meta):
    context_bits = []
    if title:
        context_bits.append('현재 프로젝트명: "%s"' % title)
    if tag:
        context_bits.append('현재 카테고리: "%s"' % tag)
    if meta:
        context_bits.append('현재 클라이언트/에이전시: "%s"' % meta)
    context = "\n".join(context_bits) if context_bits else "(아직 입력된 내용 없음)"
    return (
        "너는 광고 에이전시 아트디렉터의 포트폴리오 사이트에 들어갈 프로젝트 소개 초안을 써주는 카피라이터야.\n"
        "아래는 지금까지 입력된 정보야:\n" + context + "\n\n"
        "이 정보를 참고해서 그럴듯한 캠페인 케이스 스터디 초안을 한국어로 작성해줘. "
        "실존하는 특정 인물이나 사건을 사실인 것처럼 단정하지 말고, 포트폴리오 초안(플레이스홀더)이라는 톤을 유지해줘.\n"
        "다음 필드를 JSON으로 반환해:\n"
        "- title: 프로젝트명 (기존 값이 이미 괜찮으면 그대로 유지)\n"
        "- tag: 짧은 카테고리 (예: Brand Campaign, Digital Campaign)\n"
        "- meta: \"Client — ○○○ · Agency — ○○○\" 형식의 한 줄\n"
        "- heading: 캠페인 슬로건 한 줄\n"
        "- paragraphs: 캠페인 배경·컨셉·실행을 설명하는 한국어 문단 2~3개 (배열)"
    )


def build_translate_prompt(direction, data):
    src_lang = "한국어" if direction == "ko-en" else "영어"
    dst_lang = "영어" if direction == "ko-en" else "한국어"
    return (
        "아래는 광고 에이전시 아트디렉터 포트폴리오 사이트의 프로젝트 텍스트(JSON)야. "
        "%s로 되어 있는 텍스트를 자연스러운 %s로 번역해줘. "
        "고유명사(브랜드명, 사람 이름)는 그대로 두고, 나머지는 포트폴리오/케이스 스터디 톤을 유지해서 번역해.\n"
        "번역할 원본 JSON:\n%s\n\n"
        "동일한 필드 구조(title, tag, meta, blocks[].heading, blocks[].paragraphs)로 번역 결과를 JSON으로 반환해줘. "
        "빈 문자열이나 빈 배열은 그대로 빈 값으로 둬."
    ) % (src_lang, dst_lang, json.dumps(data, ensure_ascii=False))


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
        if parsed.path == "/ping":
            self._send_json(200, {"ok": True})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/generate", "/translate"):
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw or b"{}")
        except Exception as e:
            self._send_json(400, {"error": "bad request: %s" % e})
            return

        if parsed.path == "/generate":
            title = (payload.get("title") or "").strip()
            tag = (payload.get("tag") or "").strip()
            meta = (payload.get("meta") or "").strip()
            try:
                prompt = build_prompt(title, tag, meta)
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
