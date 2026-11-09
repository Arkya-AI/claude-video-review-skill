#!/usr/bin/env python3
"""Frame use: how much of the frame height carries content, and where it stays empty.

Usage: frame_use.py <video> <out.json> [--fps 2] [--band 0.16] [--hold 4.0] [--zone 0.115 0.77]
Bands are measured inside the zone the platform leaves visible (default for 9:16: from below the top bar to above the
username, description and audio bar, 11.5% to 77% of the height; for 16:9: 3% to 97%). The zone outside may stay plain.
Samples frames, takes each frame's most common colour as its background, marks rows where
more than 0.5% of pixels differ from it, and reports empty bands (runs of unused rows).
Flags any empty band of at least --band of the height held for --hold seconds or more.
A measurement that nominates moments to inspect; confirm on frames (review-video Step 6).
"""
import argparse, json, subprocess, sys
import numpy as np

def frames(video, fps, w=270, h=480):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", video], capture_output=True, text=True, check=True)
    W, H = [int(x) for x in probe.stdout.strip().split(",")[:2]]
    if W > H: w, h = 480, 270
    cmd = ["ffmpeg", "-v", "error", "-i", video, "-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h * 3; i = 0
    while True:
        b = p.stdout.read(n)
        if len(b) < n: break
        yield i / fps, np.frombuffer(b, np.uint8).reshape(h, w, 3).astype(int); i += 1

def analyse(img, z0=0.0, z1=1.0):
    q = (img // 16).reshape(-1, 3)
    keys, counts = np.unique(q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2], return_counts=True)
    k = keys[counts.argmax()]; bg = np.array([k // 256, (k // 16) % 16, k % 16]) * 16 + 8
    used_all = (np.abs(img - bg).sum(2) > 22).mean(1) > 0.005
    Hf = len(used_all); a, b = int(z0 * Hf), int(z1 * Hf)
    used = used_all[a:b]; H = Hf; rows = np.where(used_all)[0]
    best, start, run = (0, 0, 0), None, 0
    for y, u in enumerate(list(used) + [True]):
        if not u:
            start = y if start is None else start
        elif start is not None:
            if y - start > best[0]: best = (y - start, start + a, y + a)
            start = None
    zh = max(1, b - a)
    return {"used_share": round(float(used.mean()), 3),
            "content_top": round(rows.min() / H, 3) if len(rows) else None,
            "content_bottom": round((rows.max() + 1) / H, 3) if len(rows) else None,
            "largest_empty_band": [round(best[1] / H, 3), round(best[2] / H, 3)] if best[0] else None,
            "largest_empty_share": round(best[0] / zh, 3)}

def main():
    a = argparse.ArgumentParser(); a.add_argument("video"); a.add_argument("out")
    a.add_argument("--fps", type=float, default=2); a.add_argument("--band", type=float, default=0.16)
    a.add_argument("--hold", type=float, default=4.0); a.add_argument("--zone", type=float, nargs=2); o = a.parse_args()
    samples = []
    for t, img in frames(o.video, o.fps):
        z = o.zone or ((0.115, 0.77) if img.shape[0] > img.shape[1] else (0.03, 0.97))
        samples.append(dict(t=round(t, 2), **analyse(img, *z)))
    flags, cur = [], None
    for s in samples:
        if s["largest_empty_share"] >= o.band:
            cur = cur or {"start": s["t"], "bands": []}; cur["end"] = s["t"]; cur["bands"].append(s["largest_empty_band"])
        elif cur:
            flags.append(cur); cur = None
    if cur: flags.append(cur)
    flags = [{"start": f["start"], "end": round(f["end"] + 1 / o.fps, 2),
              "band_from": round(float(np.median([b[0] for b in f["bands"]])), 3),
              "band_to": round(float(np.median([b[1] for b in f["bands"]])), 3)}
             for f in flags if f["end"] + 1 / o.fps - f["start"] >= o.hold]
    dur = len(samples) / o.fps if samples else 0
    flagged = sum(f["end"] - f["start"] for f in flags)
    out = {"video": o.video, "fps": o.fps, "band": o.band, "hold": o.hold, "zone": o.zone or "auto", "duration_s": round(dur, 2),
           "median_used_share": round(float(np.median([s["used_share"] for s in samples])), 3) if samples else None,
           "median_content_bottom": round(float(np.median([s["content_bottom"] for s in samples if s["content_bottom"] is not None])), 3) if samples else None,
           "share_of_time_with_empty_band": round(flagged / dur, 3) if dur else None,
           "inspect": flags, "samples": samples}
    json.dump(out, open(o.out, "w"), indent=1)
    print(f"median content bottom {out['median_content_bottom']}, used share {out['median_used_share']}, "
          f"empty band >= {o.band:.0%} of the visible zone for {out['share_of_time_with_empty_band']:.0%} of the video; {len(flags)} spans to inspect")
    for f in flags: print(f"  {f['start']:6.1f}-{f['end']:6.1f} s  empty {f['band_from']:.2f}-{f['band_to']:.2f} of frame height")

if __name__ == "__main__":
    main()
