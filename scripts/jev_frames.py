#!/usr/bin/env python3
"""Every-frame pass for the Claude Video Review Skill. Checks EVERY frame of a finished film with Jev (TypeSafe), compares each
frame with the frame before it, and writes a repair list Claude can act on.

usage (Python 3.10+, numpy, opencv-python, ffmpeg; bring your own TypeSafe key: TYPESAFE_API_KEY in the environment
or in the skill folder's .env; requests go through scripts/typesafe_client.py):
  jev_frames.py prep   CONFIG.json    extract every frame, measure duplicate and frozen runs locally
  jev_frames.py run    CONFIG.json [--workers 6] [--limit N]   one Jev request per frame (cached)
  jev_frames.py report CONFIG.json    frames.csv, summary.json, repair_list.md, flagged_sheet.jpg
  jev_frames.py box    CONFIG.json [--top 12]   locate the defect on the worst frames, redraw the sheet with boxes

CONFIG keys: video, out, setting, characters {KEY: {sheet, who}}, shots [{id, start, end, cast, others, event,
silent, speed}], ignore_text [[t0, t1], ...]. Times are seconds in the delivered cut.

What Jev can judge: one picture at a time (plus the previous frame and the character sheets). It cannot judge motion
quality, timing, acting over time or sound. Absolute defect probabilities are not reliable; flags use each shot's
own baseline. Every flag is a candidate until a person or a second pass confirms it on the frames.
"""
import json, os, sys, glob, shutil, subprocess, statistics as st, concurrent.futures as cf
CLI = os.environ['TYPESAFE_CLI'].split() if os.environ.get('TYPESAFE_CLI') else [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'typesafe_client.py')]

def load(cfgp):
    c = json.load(open(cfgp)); o = c['out']
    c['_fr'], c['_req'], c['_res'], c['_sh'] = (os.path.join(o, d) for d in ('frames', 'req', 'out', 'sheets'))
    return c

def probe(video):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
                        '-of', 'csv=p=0', video], capture_output=True, text=True).stdout.strip()
    a, b = r.split('/'); return float(a) / float(b)

def shot_of(c, t):
    for s in c['shots']:
        if s['start'] - 1e-6 <= t < s['end'] - 1e-6:
            return s
    return c['shots'][-1]

def prep(c):
    for d in (c['out'], c['_fr'], c['_req'], c['_res'], c['_sh']):
        os.makedirs(d, exist_ok=True)
    fps = probe(c['video'])
    # Jev refuses requests with two large frames (two 720x1280 frames gave HTTP 400 on 9 Nov 2026); 480 px wide works
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', c['video'], '-vsync', '0', '-vf', "scale='min(480,iw)':-2", '-q:v', '3',
                    os.path.join(c['_fr'], 'f_%05d.jpg')], check=True)
    for k, v in c['characters'].items():
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', v['sheet'], '-vf', 'scale=1024:-2', '-q:v', '3',
                        os.path.join(c['_sh'], k.lower() + '.jpg')], check=True)
    import cv2, numpy as np
    frames = sorted(glob.glob(os.path.join(c['_fr'], 'f_*.jpg'))); diffs = [None]; tops = [None]; prev = None
    for f in frames:
        g = cv2.cvtColor(cv2.imread(f), cv2.COLOR_BGR2GRAY).astype('float32')
        if prev is not None:
            d = np.abs(g - prev); diffs.append(float(np.mean(d) / 255.0))
            tops.append(float(np.mean(d[: int(d.shape[0] * 0.6)]) / 255.0))  # top 60%: ignores lower-third titles
        prev = g
    json.dump({'fps': fps, 'n': len(frames), 'diff_prev': diffs, 'diff_top': tops}, open(os.path.join(c['out'], 'local.json'), 'w'))
    print(len(frames), 'frames at', fps, 'fps')

def t_of(i, fps):
    return round((i - 1) / fps, 3)

def build(c, i, fps):
    t = t_of(i, fps); s = shot_of(c, t); cast = s.get('cast', [])
    W = {k: c['characters'][k]['who'] for k in cast}
    prev_ok = i > 1 and shot_of(c, t_of(i - 1, fps))['id'] == s['id']
    state = {'image': 'FRAME', 'time_s': t, 'shot': s['id'], 'expected_people': list(W.values()),
             'other_people_allowed': s.get('others', 'nobody else'), 'setting': c['setting'],
             'note': c.get('style_note', 'Stylised 3D cartoon look and exaggerated comic faces are intended.'),
             'reference_sheets': {k: 'SHEET_' + k for k in cast}}
    if prev_ok:
        state['previous_frame'] = 'PREV is the frame shown 1/%d s before FRAME in the same shot' % round(fps)
    q = {
     'people_count': {'type': 'choice', 'instructions': 'How many humans are visible in FRAME (count partly visible people too)?',
                      'criteria': {'0': 'No humans', '1': 'One', '2': 'Two', '3': 'Three', '4+': 'Four or more', 'unclear': 'Cannot tell'}},
     'unexpected_person': {'type': 'noul', 'instructions': 'Is any human visible in FRAME who is not one of expected_people and not allowed by other_people_allowed?'},
     'hand_defect': {'type': 'noul', 'instructions': 'Does any visible hand in FRAME have the wrong number of fingers, fused or melted fingers, or an impossible shape?'},
     'face_defect': {'type': 'noul', 'instructions': 'Is any face in FRAME distorted, melted, smeared, or missing or duplicating features? Intended cartoon exaggeration does not count.'},
     'body_defect': {'type': 'noul', 'instructions': 'Does FRAME show an extra or missing limb, bodies merged together, or a body part bending impossibly?'},
    }
    if not any(a <= t < b for a, b in c.get('ignore_text', [])):
        q['text_artifact'] = {'type': 'noul', 'instructions': 'Does FRAME show readable letters, garbled text or a logo?'}
    if s.get('event'):
        q['event_visible'] = {'type': 'noul', 'instructions': s['event']}
    for k, v in (c.get('extra_questions') or {}).items():   # config-defined checks, e.g. text and layout defects for board videos (9 Nov 2026)
        q[k] = {kk: vv for kk, vv in v.items() if kk not in ('label', 'fix')}
    assets = {'FRAME': {'path': os.path.join(c['_fr'], 'f_%05d.jpg' % i)}}
    if prev_ok:
        assets['PREV'] = {'path': os.path.join(c['_fr'], 'f_%05d.jpg' % (i - 1))}
        q['jump_vs_prev'] = {'type': 'noul', 'instructions': 'Compared with PREV, does anything in FRAME change in a way a viewer would see as a glitch: a face, hair or outfit changing, an object appearing, vanishing or changing size or shape, the background or set jumping, the lighting or colour jumping, or a flash of a different image? Normal movement of characters or camera does not count.'}
        q['jump_kind'] = {'type': 'choice', 'instructions': 'If something glitches between PREV and FRAME, what is it?',
                          'criteria': {'none': 'Nothing glitches; only normal movement', 'face': 'A face or hair changes', 'outfit': 'Clothing or accessories change',
                                       'object': 'An object appears, vanishes or changes size or shape', 'background': 'The set or background jumps',
                                       'lighting': 'Lighting or colour jumps', 'other_image': 'A different image flashes in'}}
    for k in cast:
        n = k.lower(); assets['SHEET_' + k] = {'path': os.path.join(c['_sh'], n + '.jpg')}
        q['likeness_' + n] = {'type': 'choice', 'instructions': f'Compare {W[k]} in FRAME with the character in SHEET_{k} (panel 1 shows the face). Same character, face, hair, build and outfit?',
                              'criteria': {'same': 'Clearly the same character', 'close': 'Mostly the same with small differences', 'different': 'Looks like a different character or outfit', 'not_visible': 'Not visible or face hidden'}}
        q['expression_' + n] = {'type': 'choice', 'instructions': f'What is the facial expression of {W[k]} in FRAME?',
                                'criteria': {'lively': 'Lively and natural', 'comic': 'Deliberately exaggerated comic expression', 'frozen': 'Fixed, mask-like, uncanny or creepy', 'not_visible': 'Face not visible'}}
        q['mouth_' + n] = {'type': 'choice', 'instructions': f'What is the mouth of {W[k]} doing in FRAME?',
                           'criteria': {'closed': 'Closed', 'smile': 'Smiling or laughing', 'talking': 'Open as if speaking, panting or mid-word, not a smile', 'not_visible': 'Mouth not visible'}}
    return {'state': state, 'questions': q, 'assets': assets}

def call(args):
    c, i, fps = args; name = 'f_%05d' % i; out = os.path.join(c['_res'], name + '.json')
    if os.path.exists(out):
        return name, 'cached'
    req = os.path.join(c['_req'], name + '.json'); json.dump(build(c, i, fps), open(req, 'w'))
    for attempt in range(3):
        r = subprocess.run(CLI + ['evaluate', '--request', req, '--output', out], capture_output=True, text=True)
        if r.returncode == 0:
            return name, 'ok'
    return name, 'ERR ' + r.stderr.strip()[:160]

def run(c, workers, limit):
    L = json.load(open(os.path.join(c['out'], 'local.json'))); n = L['n'] if not limit else min(limit, L['n'])
    with cf.ThreadPoolExecutor(workers) as ex:
        bad = 0
        for name, stt in ex.map(call, [(c, i, L['fps']) for i in range(1, n + 1)]):
            if stt.startswith('ERR'):
                bad += 1; print(name, stt, flush=True)
    print('done', n, 'frames,', bad, 'errors', flush=True)

def runs(ts, gap):
    out, cur = [], []
    for t in ts:
        if cur and t - cur[-1] > gap + 1e-6:
            out.append(cur); cur = []
        cur.append(t)
    if cur:
        out.append(cur)
    return out

def report(c):
    L = json.load(open(os.path.join(c['out'], 'local.json'))); fps = L['fps']; dt = 1.0 / fps
    rows, usage = [], [0, 0]
    for f in sorted(glob.glob(os.path.join(c['_res'], 'f_*.json'))):
        d = json.load(open(f)); i = int(os.path.basename(f)[2:7]); t = t_of(i, fps); s = shot_of(c, t)
        usage[0] += d.get('usage', {}).get('input_tokens', 0); usage[1] += d.get('usage', {}).get('output_tokens', 0)
        r = {'frame': i, 't': t, 'shot': s['id'], 'diff_prev': L['diff_prev'][i - 1], 'diff_top': L.get('diff_top', L['diff_prev'])[i - 1]}
        for k, v in d['answers'].items():
            if v['type'] == 'noul':
                r[k] = v['noul']
            elif v['type'] == 'choice':
                r[k] = v['choice']; P = v['probabilities']
                if k.startswith('likeness_'): r[k + '_bad'] = P.get('different', 0)
                if k.startswith('expression_'): r[k + '_frozen'] = P.get('frozen', 0)
                if k.startswith('mouth_'): r[k + '_talk'] = P.get('talking', 0)
                if k == 'jump_kind': r['jump_kind_p'] = max(P.values())
        rows.append(r)
    import csv
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in ('frame', 't', 'shot', 'diff_prev'), k))
    with open(os.path.join(c['out'], 'frames.csv'), 'w', newline='') as h:
        w = csv.DictWriter(h, keys); w.writeheader(); w.writerows(rows)
    items, summ = [], {'frames_read': len(rows), 'frames_total': L['n'], 'fps': fps, 'usage': usage, 'shots': {}}
    def add(sid, t0, t1, kind, what, fix, frames, sev):
        items.append({'shot': sid, 't0': round(t0, 2), 't1': round(t1, 2), 'kind': kind, 'what': what, 'fix': fix,
                      'frames': frames[:6], 'severity': sev})
    over = lambda t: any(a - 0.2 <= t <= b for a, b in c.get('ignore_text', []))
    summ['detected_cuts'] = []
    for s in c['shots']:
        R = [r for r in rows if r['shot'] == s['id']]
        if not R:
            continue
        sh = {'frames': len(R), 't': [R[0]['t'], R[-1]['t']]}
        dd = [r['diff_prev'] for r in R if r['diff_prev']]
        cut_th = max(0.08, 6 * st.median(dd)) if dd else 1
        cuts = {r['frame'] for r in R if (r['diff_prev'] or 0) >= cut_th}
        if R[0]['frame'] > 1:
            cuts.add(R[0]['frame'])
        for r in R:  # one frame either side of a configured shot start also counts as the cut
            if abs(r['t'] - s['start']) <= 1.5 * dt and (r['diff_prev'] or 0) >= 0.5 * cut_th:
                cuts.add(r['frame'])
        sh['cuts_inside_shot'] = [round(r['t'], 2) for r in R if r['frame'] in cuts and r['frame'] != R[0]['frame']]
        summ['detected_cuts'] += sh['cuts_inside_shot']
        for r in R:
            if r['frame'] in cuts or over(r['t']):
                r['jump_vs_prev'] = 0
        small = [r for r in R if (r['diff_top'] if r['diff_top'] is not None else 1) < 0.0008]
        dup_share = len(small) / len(R)
        sh['duplicate_share'] = round(dup_share, 2)
        base = lambda k: st.median([r.get(k, 0) for r in R if k in r] or [0])
        for k, label, fix in (('hand_defect', 'hand or finger defect', 'cut the frames or retake the shot'),
                              ('face_defect', 'face distortion', 'cut the frames or retake the shot'),
                              ('body_defect', 'merged or broken body', 'cut the frames (usually 2 to 4 at a contact) or retake'),
                              ('unexpected_person', 'unexpected person in frame', 'retake with a CAST line; pass only this shot\'s sheets'),
                              ('text_artifact', 'garbled text or logo', 'overlay a clean graphic or crop'),
                              ('jump_vs_prev', 'visible jump from the previous frame', 'trim at the jump or hide it with a cut on action')) + \
                             tuple((k, v.get('label', k), v.get('fix', 'inspect the frames and fix the layout')) for k, v in (c.get('extra_questions') or {}).items() if v.get('type') == 'noul'):
            b = base(k); th = max(0.6, b + 0.25)
            hits = [r for r in R if r.get(k, 0) >= th and (k != 'jump_vs_prev' or r.get('jump_kind') != 'none')]
            sh[k] = {'baseline': round(b, 2), 'flagged': len(hits)}
            for g in runs([r['t'] for r in hits], 2 * dt):
                fr = [r['frame'] for r in hits if g[0] <= r['t'] <= g[-1]]
                kinds = sorted({r.get('jump_kind') for r in hits if g[0] <= r['t'] <= g[-1] and r.get('jump_kind')})
                add(s['id'], g[0], g[-1] + dt, k, label + (' (' + ', '.join(kinds) + ')' if kinds else ''), fix, fr,
                    'major' if len(g) >= 2 or k in ('unexpected_person', 'jump_vs_prev') else 'minor')
        for k in s.get('cast', []):
            n = k.lower(); who = c['characters'][k]['who']
            vis = [r for r in R if r.get('likeness_' + n) not in (None, 'not_visible')]
            diff = [r for r in vis if r.get('likeness_' + n) == 'different']
            sh['likeness_' + n] = {'visible': len(vis), 'different': len(diff)}
            for g in runs([r['t'] for r in diff], 2 * dt):
                if len(g) >= 3:
                    add(s['id'], g[0], g[-1] + dt, 'likeness', f'{who} does not match the sheet', 'retake with the sheet attached; medium framing', [r['frame'] for r in diff if g[0] <= r['t'] <= g[-1]], 'major')
            fz = [r for r in R if r.get('expression_' + n + '_frozen', 0) >= 0.5]
            for g in runs([r['t'] for r in fz], 2 * dt):
                if g[-1] - g[0] >= 0.5:
                    add(s['id'], g[0], g[-1] + dt, 'frozen_face', f'{who} looks frozen or mask-like', 'give a physical acting beat; retake', [r['frame'] for r in fz if g[0] <= r['t'] <= g[-1]], 'major')
            if s.get('silent', True):
                tk = [r for r in R if r.get('mouth_' + n) == 'talking']
                for g in runs([r['t'] for r in tk], 2 * dt):
                    if g[-1] - g[0] >= 0.4:
                        add(s['id'], g[0], g[-1] + dt, 'mouth', f'{who} mouth moves as if talking in a silent shot', 'add "lips closed" and an action for this character; retake', [r['frame'] for r in tk if g[0] <= r['t'] <= g[-1]], 'major' if g[-1] - g[0] >= 1.0 else 'minor')
            sh['mouth_' + n] = dict((m, sum(r.get('mouth_' + n) == m for r in R)) for m in ('closed', 'smile', 'talking', 'not_visible'))
        if s.get('event'):
            pk = max(R, key=lambda r: r.get('event_visible', 0)); sh['event_peak'] = [round(pk.get('event_visible', 0), 2), pk['t']]
            if pk.get('event_visible', 0) < 0.6:
                add(s['id'], R[0]['t'], R[-1]['t'] + dt, 'event_missing', 'the key action was not seen in any frame: ' + s['event'], 'check the shot; rewrite as cause and effect; retake', [pk['frame']], 'major')
        if abs(s.get('speed', 1.0) - 1.0) > 0.01:
            add(s['id'], s['start'], s['end'], 'speed', f"shot plays at {s['speed']}x, not natural speed", 're-prompt for real-time motion; never slow in the edit', [], 'major')
        frz = [r['t'] for r in R if (r['diff_top'] if r['diff_top'] is not None else 1) < 0.0008]
        long_frz = 0
        for g in runs(frz, 2 * dt):
            if g[-1] - g[0] >= 0.5:
                long_frz += len(g)
                add(s['id'], g[0] - dt, g[-1] + dt, 'freeze', f'picture is frozen for {g[-1] - g[0] + dt:.1f} s', 'use moving footage; freeze only as a planned story beat', [], 'major')
        # retimed (slowed) footage repeats near-copies of frames: the frame-to-frame change dips far below both neighbours
        dv = [r['diff_top'] for r in R if r['diff_top'] is not None]
        dips = sum(1 for k in range(1, len(dv) - 1) if dv[k] < 0.35 * min(dv[k - 1], dv[k + 1]) and min(dv[k - 1], dv[k + 1]) > 0.002)
        share = dips / max(1, len(dv)); sh['repeat_dip_share'] = round(share, 2)
        if share >= 0.10:
            add(s['id'], s['start'], s['end'], 'retimed', f'{share:.0%} of frames are near-repeats: footage was slowed or has judder', 'play at natural speed; re-prompt for real-time motion', [], 'major')
        summ['shots'][s['id']] = sh
    items.sort(key=lambda x: (x['t0'], x['kind']))
    summ['repair_items'] = items
    json.dump(summ, open(os.path.join(c['out'], 'summary.json'), 'w'), indent=1)
    lines = ['# Jev full-frame repair list', '', f"Video: `{c['video']}`", f"Frames read: {len(rows)} of {L['n']} at {fps:g} fps. Tokens in/out: {usage[0]:,} / {usage[1]:,}.",
             'Every item is a candidate until confirmed on the frames or by a second pass. Jev judges single frames; motion, timing, acting over time and sound are judged elsewhere.', '',
             '| # | Shot | Time (s) | Frames | Issue | Suggested fix | Severity |', '|---|---|---|---|---|---|---|']
    for n, x in enumerate(items, 1):
        lines.append(f"| {n} | {x['shot']} | {x['t0']:.2f} to {x['t1']:.2f} | {', '.join(map(str, x['frames'])) or '-'} | {x['what']} | {x['fix']} | {x['severity']} |")
    open(os.path.join(c['out'], 'repair_list.md'), 'w').write('\n'.join(lines) + '\n')
    sheet(c, items)
    print('\n'.join(lines))

def sheet(c, items, boxes=None):
    import cv2, numpy as np
    picks = []
    for x in items:
        for f in x['frames'][:2]:
            picks.append((f, x))
    picks = picks[:40]
    if not picks:
        return
    tiles = []
    for f, x in picks:
        im = cv2.imread(os.path.join(c['_fr'], 'f_%05d.jpg' % f)); h, w = im.shape[:2]
        if boxes and f in boxes:
            b = boxes[f]; cv2.rectangle(im, (int(b[0] * w), int(b[1] * h)), (int(b[2] * w), int(b[3] * h)), (0, 0, 255), 3)
        im = cv2.resize(im, (240, int(240 * h / w)))
        cv2.rectangle(im, (0, 0), (240, 36), (0, 0, 0), -1)
        cv2.putText(im, f"f{f} {x['shot']} {x['kind']}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
        cv2.putText(im, f"{x['t0']:.2f}s", (4, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)
        tiles.append(im)
    H = max(t.shape[0] for t in tiles); tiles = [cv2.copyMakeBorder(t, 0, H - t.shape[0], 0, 0, cv2.BORDER_CONSTANT) for t in tiles]
    rowsimg = [np.hstack(tiles[k:k + 8] + [np.zeros_like(tiles[0])] * (8 - len(tiles[k:k + 8]))) for k in range(0, len(tiles), 8)]
    cv2.imwrite(os.path.join(c['out'], 'flagged_sheet.jpg'), np.vstack(rowsimg), [cv2.IMWRITE_JPEG_QUALITY, 85])

def box(c, top):
    summ = json.load(open(os.path.join(c['out'], 'summary.json'))); its = [x for x in summ['repair_items'] if x['frames']]
    its.sort(key=lambda x: x['severity'] != 'major'); bd = os.path.join(c['out'], 'box'); os.makedirs(bd, exist_ok=True); boxes = {}
    for x in its[:top]:
        f = x['frames'][0]; req = os.path.join(bd, f'f{f}_req.json'); out = os.path.join(bd, f'f{f}.json')
        body = {'state': {'image': 'FRAME', 'issue_to_locate': x['what'], 'setting': c['setting']},
                'questions': {'where': {'type': 'box', 'instructions': 'Locate the area of FRAME that shows the issue_to_locate.'}},
                'assets': {'FRAME': {'path': os.path.join(c['_fr'], 'f_%05d.jpg' % f)}}}
        json.dump(body, open(req, 'w'))
        if not os.path.exists(out):
            subprocess.run(CLI + ['evaluate', '--request', req, '--output', out], capture_output=True, text=True)
        try:
            b = json.load(open(out))['answers']['where'].get('box')
            if b: boxes[f] = [b['left'], b['top'], b['right'], b['bottom']]
        except Exception:
            pass
    boxes = {k: v for k, v in boxes.items() if v}
    sheet(c, summ['repair_items'], boxes); print('boxes', len(boxes))

if __name__ == '__main__':
    cmd, c = sys.argv[1], load(sys.argv[2]); a = sys.argv
    opt = lambda k, d: int(a[a.index(k) + 1]) if k in a else d
    {'prep': lambda: prep(c), 'run': lambda: run(c, opt('--workers', 6), opt('--limit', 0)),
     'report': lambda: report(c), 'box': lambda: box(c, opt('--top', 12))}[cmd]()
