#!/usr/bin/env python3
"""Layer 0 technical QC for a finished video. Measurements only: they nominate
moments to inspect; they do not prove a viewer-visible defect on their own.

usage: tech_qc.py VIDEO OUT_DIR [--script script.txt] [--target-lufs -14]
needs: ffmpeg/ffprobe, numpy, opencv-python. ASR read-back uses faster-whisper
(WHISPER_MODEL, default "small"); if it is missing and PARAKEET_DIR points to a
sherpa-onnx Parakeet model, that is used instead; otherwise ASR is skipped.
Writes OUT_DIR/tech_qc.json, contact_sheet.jpg, seams/*.jpg
"""
import argparse, json, os, re, subprocess, difflib
import numpy as np, cv2

PARAKEET = os.path.join(os.path.expanduser(os.environ.get("PARAKEET_DIR", "~/models/parakeet")), "")


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(f):
    j = json.loads(sh(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", f]).stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), {})
    fr = lambda r: round(eval(r), 3) if r and r != "0/0" else None
    return {"width": v.get("width"), "height": v.get("height"), "fps": fr(v.get("r_frame_rate")),
            "avg_fps": fr(v.get("avg_frame_rate")), "vcodec": v.get("codec_name"),
            "v_duration": float(v.get("duration", 0) or 0), "acodec": a.get("codec_name"),
            "a_rate": a.get("sample_rate"), "a_channels": a.get("channels"),
            "a_duration": float(a.get("duration", 0) or 0), "has_audio": bool(a),
            "duration": float(j["format"].get("duration", 0)), "bitrate_kbps": int(j["format"].get("bit_rate", 0)) // 1000}


def video_scan(f, out):
    cap = cv2.VideoCapture(f); fps = cap.get(5) or 30
    prev = None; diffs = []; tiles = []; frames = {}; n = 0; luma = []; sharp = []
    step = max(1, int(fps * 1.5))
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        small = cv2.resize(fr, (180, 320) if fr.shape[0] > fr.shape[1] else (320, 180))
        g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
        luma.append(float(g.mean()))
        if prev is not None:
            diffs.append(float(np.abs(g - prev).mean()))
        prev = g
        if n % int(fps) == 0:
            sharp.append(float(cv2.Laplacian(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()))
        frames[n] = cv2.resize(fr, (270, 480) if fr.shape[0] > fr.shape[1] else (480, 270))
        if len(frames) > 3:
            frames.pop(min(frames))
        if n % step == 0:
            t = frames[n].copy(); cv2.putText(t, f"{n / fps:.1f}s", (6, 24), 0, 0.7, (0, 255, 255), 2); tiles.append(t)
        if diffs and n > 1:
            d = diffs[-1]
            if len(diffs) > 30:
                med = float(np.median(diffs[-300:]))
                if d > 8 * med and d > 4:  # spike: cut, jump or glitch -> save the before/after pair
                    os.makedirs(f"{out}/seams", exist_ok=True)
                    pair = np.hstack([frames[n - 1], frames[n]])
                    cv2.imwrite(f"{out}/seams/seam_{n / fps:07.2f}s.jpg", pair, [cv2.IMWRITE_JPEG_QUALITY, 85])
        n += 1
    d = np.array(diffs) if diffs else np.zeros(1)
    med = float(np.median(d))
    spikes = [round((i + 1) / fps, 2) for i, v in enumerate(d) if v > 8 * med and v > 4]
    cols = 8 if tiles and tiles[0].shape[0] > tiles[0].shape[1] else 5
    while tiles and len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    if tiles:
        cv2.imwrite(f"{out}/contact_sheet.jpg", np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]),
                    [cv2.IMWRITE_JPEG_QUALITY, 80])
    dup = float((d < 0.03).mean())
    return {"frames": n, "fps_read": round(fps, 3), "duplicate_frame_share": round(dup, 3),
            "duplicate_note": "about 0.2 at 30 fps usually means a 24 fps source padded by duplication (judder); intentional holds also count",
            "jump_spikes_s": spikes, "median_frame_diff": round(med, 3),
            "sharpness_laplacian_median": round(float(np.median(sharp)), 1) if sharp else None,
            "sharpness_min_s": (int(np.argmin(sharp)) if sharp else None),
            "dark_frames_share": round(float((np.array(luma) < 8).mean()), 3)}


def ffmpeg_detect(f):
    r = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", f, "-vf", "blackdetect=d=0.2:pix_th=0.08,freezedetect=n=0.003:d=0.8",
            "-af", "ebur128=peak=true,silencedetect=n=-45dB:d=0.7", "-f", "null", "-"]).stderr
    num = lambda pat: [float(x) for x in re.findall(pat, r)]
    integ = re.findall(r"I:\s+(-?[\d.]+) LUFS", r)
    lra = re.findall(r"LRA:\s+([\d.]+) LU", r)
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)
    return {"black_starts_s": num(r"black_start:([\d.]+)"), "freeze_starts_s": num(r"freeze_start: ([\d.]+)"),
            "freeze_durations_s": num(r"freeze_duration: ([\d.]+)"),
            "silence_starts_s": num(r"silence_start: ([\d.]+)"), "silence_durations_s": num(r"silence_duration: ([\d.]+)"),
            "integrated_lufs": float(integ[-1]) if integ else None, "lra_lu": float(lra[-1]) if lra else None,
            "true_peak_dbfs": float(tp[-1]) if tp else None}


def audio_scan(f):
    x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-ac", "1", "-ar", "48000", "-f", "f32le", "-"],
                                     capture_output=True).stdout, np.float32)
    if not len(x):
        return {"audio_decoded": False}
    dd = np.abs(np.diff(x)); loc = np.convolve(dd, np.ones(480) / 480, "same") + 1e-4
    cl = np.where((dd > 0.15) & (dd > 12 * loc))[0]
    ev = []
    for i in cl:
        if not ev or i - ev[-1] > 2400:
            ev.append(i)
    clip = int((np.abs(x) > 0.999).sum())
    return {"audio_decoded": True, "click_candidates": len(ev), "click_times_s": [round(i / 48000, 2) for i in ev[:40]],
            "clipped_samples": clip, "sample_peak": round(float(np.abs(x).max()), 3),
            "click_note": "candidates are sample discontinuities; confirm by listening at each time"}


def transcribe(f):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    m = WhisperModel(os.environ.get("WHISPER_MODEL", "small"), device="auto", compute_type="int8")
    segs, _ = m.transcribe(f, vad_filter=True)
    return " ".join(s.text.strip() for s in segs)


def asr(f, script):
    text = transcribe(f)
    if text is not None:
        return readback({"transcript": text, "asr_engine": "faster-whisper"}, script)
    try:
        import sherpa_onnx
    except ImportError:
        return {"asr": "skipped (install faster-whisper: pip install faster-whisper)"}
    if not os.path.isdir(PARAKEET):
        return {"asr": "skipped (no faster-whisper, and PARAKEET_DIR not set)"}
    P = PARAKEET
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(encoder=P + "encoder.int8.onnx", decoder=P + "decoder.int8.onnx",
                                                        joiner=P + "joiner.int8.onnx", tokens=P + "tokens.txt",
                                                        model_type="nemo_transducer", num_threads=8)
    y = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                                     capture_output=True).stdout, np.float32)
    # Parakeet fails on long inputs (seen on a 7:45 video, 2026-10-13): decode in 60 s pieces
    texts = []
    for i in range(0, len(y), 16000 * 60):
        s = rec.create_stream(); s.accept_waveform(16000, y[i:i + 16000 * 60]); rec.decode_stream(s); texts.append(s.result.text.strip())
    return readback({"transcript": " ".join(t for t in texts if t), "asr_engine": "parakeet"}, script)


def readback(out, script):
    if script:
        norm = lambda z: re.findall(r"[a-z]+", z.lower())
        hyp, ref = norm(out["transcript"]), norm(open(script).read())
        sm = difflib.SequenceMatcher(None, ref, hyp)
        out["readback_match"] = round(sm.ratio(), 3)
        out["readback_diffs"] = [(op, " ".join(ref[a:b]), " ".join(hyp[c:e])) for op, a, b, c, e in sm.get_opcodes() if op != "equal"][:40]
        out["asr_note"] = "a match does not prove correct pronunciation; listen to brand and technical terms"
    return out


def main():
    a = argparse.ArgumentParser()
    a.add_argument("video"); a.add_argument("out")
    a.add_argument("--script"); a.add_argument("--target-lufs", type=float, default=-14.0)
    x = a.parse_args()
    os.makedirs(x.out, exist_ok=True)
    r = {"video": os.path.abspath(x.video), "probe": probe(x.video)}
    r["video_scan"] = video_scan(x.video, x.out)
    r["ffmpeg"] = ffmpeg_detect(x.video)
    r["audio"] = audio_scan(x.video) if r["probe"]["has_audio"] else {"audio_decoded": False}
    r["asr"] = asr(x.video, x.script) if r["probe"]["has_audio"] else {}
    p, fl = r["probe"], []
    if p["has_audio"] and abs(p["v_duration"] - p["a_duration"]) > 0.3:
        fl.append(f"audio and video durations differ by {abs(p['v_duration'] - p['a_duration']):.2f} s")
    if r["video_scan"]["duplicate_frame_share"] > 0.1:
        fl.append("high duplicate-frame share: check for judder")
    if r["video_scan"]["jump_spikes_s"]:
        fl.append(f"{len(r['video_scan']['jump_spikes_s'])} frame-jump spikes: inspect seams/ images")
    lu = r["ffmpeg"]["integrated_lufs"]
    if lu is not None and abs(lu - x.target_lufs) > 1.0:
        fl.append(f"loudness {lu} LUFS vs chosen target {x.target_lufs}")
    tp = r["ffmpeg"]["true_peak_dbfs"]
    if tp is not None and tp > -1.0:
        fl.append(f"true peak {tp} dBFS above -1")
    if r["audio"].get("click_candidates"):
        fl.append(f"{r['audio']['click_candidates']} click candidates: listen at click_times_s")
    if r["ffmpeg"]["freeze_starts_s"]:
        fl.append("frozen-picture intervals: check they are intentional")
    if p["height"] and min(p["width"], p["height"]) < 1080:
        fl.append(f"delivery resolution {p['width']}x{p['height']} below 1080 on the short side")
    r["inspect"] = fl
    json.dump(r, open(f"{x.out}/tech_qc.json", "w"), indent=2)
    print(json.dumps({"inspect": fl, "lufs": lu, "true_peak": tp, "clicks": r["audio"].get("click_candidates"),
                      "dup_share": r["video_scan"]["duplicate_frame_share"], "spikes": r["video_scan"]["jump_spikes_s"]}, indent=1))


if __name__ == "__main__":
    main()
