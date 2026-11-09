#!/usr/bin/env python3
"""Pick frames for the independent still-image pass (GPT via Codex).

Mixes random frames with frames at moments to check, so the frame reviewer
does not know which is which. Also writes a face crop per frame when OpenCV
finds a face, and a 360 px phone-size copy for legibility checks.

usage: sample_frames.py VIDEO OUT_DIR [--at 11.03,17.7] [--random 8] [--seed 7]
"""
import argparse, os, random
import cv2


def main():
    a = argparse.ArgumentParser()
    a.add_argument("video"); a.add_argument("out")
    a.add_argument("--at", default="", help="comma-separated seconds to check (seams, flags)")
    a.add_argument("--random", type=int, default=8)
    a.add_argument("--seed", type=int, default=7)
    x = a.parse_args()
    os.makedirs(x.out, exist_ok=True)
    cap = cv2.VideoCapture(x.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    random.seed(x.seed)
    idx = set(random.sample(range(n), min(x.random, n)))
    for s in filter(None, x.at.split(",")):
        f = int(round(float(s) * fps))
        idx.update(i for i in (f - 1, f) if 0 <= i < n)  # before/after pair
    try:
        face = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    except AttributeError:
        face = None  # OpenCV build without cascades: skip face crops
    written = []
    for i in sorted(idx):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, fr = cap.read()
        if not ok:
            continue
        t = i / fps
        name = f"t{t:07.2f}s"
        cv2.imwrite(f"{x.out}/{name}.jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 90])
        h, w = fr.shape[:2]
        phone = cv2.resize(fr, (360, int(360 * h / w)))
        cv2.imwrite(f"{x.out}/{name}_phone.jpg", phone, [cv2.IMWRITE_JPEG_QUALITY, 85])
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        faces = face.detectMultiScale(g, 1.1, 6, minSize=(w // 10, w // 10)) if face is not None else []
        if len(faces):
            fx, fy, fw, fh = max(faces, key=lambda r: r[2] * r[3])
            p = int(0.35 * fw)
            crop = fr[max(0, fy - p):fy + fh + p, max(0, fx - p):fx + fw + p]
            cv2.imwrite(f"{x.out}/{name}_face.jpg", cv2.resize(crop, (768, int(768 * crop.shape[0] / crop.shape[1]))),
                        [cv2.IMWRITE_JPEG_QUALITY, 92])
        written.append(name)
    print(f"{len(written)} frames -> {x.out}")


if __name__ == "__main__":
    main()
