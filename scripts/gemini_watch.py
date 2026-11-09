#!/usr/bin/env python3
"""Send a video (with its audio) to Gemini and save the reply.

Usage: gemini_watch.py VIDEO PROMPT_FILE OUT_FILE [--model M] [--fps N] [--audio-only] [--json]
Key: GEMINI_API_KEY from the environment, else the .env file in the skill folder, else ~/.gemini/.env.
Standard library only.
"""
import argparse, json, mimetypes, os, sys, time, urllib.request, urllib.error

BASE = "https://generativelanguage.googleapis.com"


def key():
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if k:
        return k
    skill_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    for p in (skill_env, os.path.expanduser("~/.gemini/.env")):
        if os.path.exists(p):
            for line in open(p):
                line = line.strip()
                if line.startswith(("GEMINI_API_KEY=", "GOOGLE_API_KEY=")):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("no GEMINI_API_KEY: export it or put GEMINI_API_KEY=... in the skill folder's .env")


def req(url, data=None, headers=None, method=None):
    r = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(r, timeout=600) as resp:
            return resp.headers, resp.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:2000]}")


def upload(path, k):
    size = os.path.getsize(path)
    mime = mimetypes.guess_type(path)[0] or "video/mp4"
    h, _ = req(f"{BASE}/upload/v1beta/files?key={k}",
               data=json.dumps({"file": {"display_name": os.path.basename(path)}}).encode(),
               headers={"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
                        "X-Goog-Upload-Header-Content-Length": str(size),
                        "X-Goog-Upload-Header-Content-Type": mime, "Content-Type": "application/json"},
               method="POST")
    up = h.get("X-Goog-Upload-URL") or h.get("x-goog-upload-url")
    _, body = req(up, data=open(path, "rb").read(),
                  headers={"Content-Length": str(size), "X-Goog-Upload-Offset": "0",
                           "X-Goog-Upload-Command": "upload, finalize"}, method="POST")
    f = json.loads(body)["file"]
    while f.get("state") == "PROCESSING":
        time.sleep(3)
        _, body = req(f"{BASE}/v1beta/{f['name']}?key={k}")
        f = json.loads(body)
    if f.get("state") != "ACTIVE":
        sys.exit(f"file not active: {f}")
    return f["uri"], mime


def main():
    a = argparse.ArgumentParser()
    a.add_argument("video"); a.add_argument("prompt_file"); a.add_argument("out")
    a.add_argument("--model", default="gemini-3.1-pro-preview")
    a.add_argument("--fps", type=float, default=None)
    a.add_argument("--json", action="store_true", help="ask for application/json output")
    a.add_argument("--temperature", type=float, default=0.2)
    x = a.parse_args()
    k = key()
    uri, mime = upload(x.video, k)
    part = {"file_data": {"file_uri": uri, "mime_type": mime}}
    if x.fps:
        part["video_metadata"] = {"fps": x.fps}
    body = {"contents": [{"role": "user", "parts": [part, {"text": open(x.prompt_file).read()}]}],
            "generationConfig": {"temperature": x.temperature}}
    if x.json:
        body["generationConfig"]["responseMimeType"] = "application/json"
    t = time.time()
    _, resp = req(f"{BASE}/v1beta/models/{x.model}:generateContent?key={k}",
                  data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    r = json.loads(resp)
    text = "".join(p.get("text", "") for c in r.get("candidates", []) for p in c.get("content", {}).get("parts", []))
    open(x.out, "w").write(text)
    meta = {"model": x.model, "fps": x.fps, "seconds": round(time.time() - t, 1), "usage": r.get("usageMetadata")}
    open(x.out + ".meta.json", "w").write(json.dumps(meta, indent=2))
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
