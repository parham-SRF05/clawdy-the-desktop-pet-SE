"""Tests for everything that doesn't need a window: behaviour, settings, pixel art."""
import json
import os
import random
import re
import sys
import tempfile
import time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, ROOT)
from pet import behavior, config, sprites

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += not ok
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + str(detail)) if detail else ''))


# --- behaviour ------------------------------------------------------------------------------
cfg = config._merge(config.DEFAULTS, {})
AREA = (0, 1920, 1140)
SIZE = (96, 64)


def run(pet, seconds, t0=0.0, react=None):
    t = t0
    for i in range(int(seconds * 60)):
        if i == 0 and react:
            pet.react(t, react)
        pet.update(t, 1 / 60)
        t += 1 / 60
    return t


P = behavior.Pet(cfg, AREA, SIZE, 0.0, random.Random(4))
xs, anims = [], set()
t = 0.0
for _ in range(60 * 120):
    P.update(t, 1 / 60)
    xs.append(P.x)
    anims.add(P.anim)
    t += 1 / 60
check('never falls asleep by default: still lively after 2 minutes', 'sleep' not in anims and not P.asleep)
check('walks along the taskbar', max(xs) - min(xs) > 400, (round(min(xs)), round(max(xs))))
check('does cute tricks while wandering', len({'wave', 'dance', 'look', 'happy', 'sit', 'celebrate'} & anims) >= 3, anims)
check('smooth: no jumps between frames', max(abs(a - b) for a, b in zip(xs, xs[1:])) < 2)

zone = behavior.walk_zone(AREA, 40, 'center')
check('walking area: 40% in the middle', zone == (576.0, 1344.0, 1140), zone)
check('walking area: left and right', behavior.walk_zone(AREA, 25, 'left')[:2] == (0, 480.0)
      and behavior.walk_zone(AREA, 25, 'right')[:2] == (1440.0, 1920))
P = behavior.Pet(cfg, zone, SIZE, 0.0, random.Random(8), screen=AREA)
xs = []
t = 0.0
for _ in range(60 * 90):
    P.update(t, 1 / 60)
    xs.append(P.x)
    t += 1 / 60
check('stays inside its walking area', min(xs) >= 576 + 48 - 0.01 and max(xs) <= 1344 - 48 + 0.01, (min(xs), max(xs)))
P.grab(t, 100, 1140)
P.release(t)
check('can be dragged outside its area', P.x == 100, P.x)
run(P, 30, t0=t)
check('then walks back into its area by itself', 624 <= P.x <= 1296, round(P.x))

P = behavior.Pet(dict(cfg, sleep_after_seconds=20), AREA, SIZE, 0.0, random.Random(1))
run(P, 25)
check('optional sleep still works when turned on', P.asleep)
P.hint = 'type'
run(P, 1, t0=25)
check('wakes up and copies you when you start typing', not P.asleep and P.anim == 'type', P.anim)

P = behavior.Pet(cfg, AREA, SIZE, 0.0, random.Random(3))
run(P, 3)
P.hover(3.0, True)
x0 = P.x
t = run(P, 2, t0=3.0)
check('hover: stops, waves hello, stays put', P.x == x0 and P.target is None, P.anim)
P.hover(t, False)
run(P, 20, t0=t)
check('after hover: walks again', P.x != x0)

P = behavior.Pet(cfg, AREA, SIZE, 0.0, random.Random(2))
run(P, 0.5, react='done')
check('celebrates with a bubble when something finishes', P.anim == 'celebrate' and P.bubble and P.bubble[0] == 'Done!')
run(P, 3, t0=0.5)
t = run(P, 20, t0=3.5)
check('after celebrating it keeps walking around', P.target is not None or P.busy_reacting(t) or P.anim in (
    'walk', 'idle', 'look', 'wave', 'dance', 'happy', 'sit', 'celebrate'), P.anim)

P = behavior.Pet(cfg, AREA, SIZE, 0.0, random.Random(5))
P.grab(0.0, 500, 800)
P.update(0.02, 0.02)
check('dragged: dangling pose in the air', P.anim == 'drag' and P.lift == 340)
P.release(0.1)
run(P, 2, t0=0.1)
check('dropped: falls back onto the taskbar', P.lift == 0 and P.mode == 'ground')

P = behavior.Pet(cfg, AREA, SIZE, 0.0, random.Random(6))
t, shown = 0.0, []
for i in range(60 * 3):
    P.hint = ['read', 'type'][(i // 6) % 2]   # you flicking between two apps
    P.update(t, 1 / 60)
    shown.append(P.anim)
    t += 1 / 60
check('switching apps quickly does not flicker', sum(1 for a, b in zip(shown, shown[1:]) if a != b) <= 4)

P = behavior.Pet(dict(cfg, wander=False, tricks=False, copy_my_apps=False), AREA, SIZE, 0.0, random.Random(7))
x0 = P.x
run(P, 10)
check('settings: stays put when walking and tricks are off', P.anim == 'idle' and P.x == x0, P.anim)

# --- settings -------------------------------------------------------------------------------
c = config._merge(config.DEFAULTS, {'scale': 99, 'walk_speed': 'fast', 'bubbles': 0, 'nonsense': 1,
                                    'walk_width_percent': 3, 'messages': {'done': 'Yay!'}})
check('settings are validated', c['scale'] == 8 and c['walk_speed'] == 1.0 and c['bubbles'] is False
      and 'nonsense' not in c and c['walk_width_percent'] == 10 and c['messages']['done'] == 'Yay!'
      and c['messages']['hello'] == 'Hi!')
check('defaults: lively, full taskbar', config.DEFAULTS['sleep_after_seconds'] == 0 and config.DEFAULTS['tricks']
      and config.DEFAULTS['walk_width_percent'] == 100)
p = os.path.join(tempfile.mkdtemp(), 'config.json')
with open(p, 'w') as f:
    f.write('{broken')
check('a broken settings file is not overwritten',
      config.load(p)['scale'] == config.DEFAULTS['scale'] and open(p).read() == '{broken')

# --- pixel art ------------------------------------------------------------------------------
frames = sprites.build_frames({'body': '#6aa3ff'})
sizes = {(len(f), len(f[0])) for anim in frames.values() for f in anim}
check('every frame is 48x32', sizes == {(32, 48)}, sizes)
idle = sprites.build_frames()['idle'][0]
body = sprites.DEFAULT_COLORS['body']
cols = [x for x in range(sprites.W) if any(idle[y][x] == body for y in range(sprites.H))]
rows = [y for y in range(sprites.H) if any(c == body for c in idle[y])]
check('the square character: 32 px wide with arms, 20 px tall, standing on the ground',
      (cols[0], cols[-1], rows[0], rows[-1]) == (8, 39, 12, 31))
check('two tall eyes', all(idle[y][x] == sprites.DEFAULT_COLORS['eye'] for x in (16, 17, 30, 31) for y in range(16, 20)))
check('four legs', [x for x in range(sprites.W) if idle[31][x] == body] == [14, 15, 18, 19, 28, 29, 32, 33])
colours = {c for anim in frames.values() for f in anim for row in f for c in row if c}
check('all colours valid, none equal to the see-through colour',
      all(re.fullmatch(r'#[0-9a-f]{6}', c) for c in colours) and '#ff00fe' not in colours)
check('colour overrides are applied', '#6aa3ff' in colours and body not in colours)
needed = {'idle', 'walk', 'sit', 'think', 'type', 'read', 'command', 'web', 'alert', 'celebrate', 'wave', 'happy',
          'error', 'sleep', 'drag', 'fall', 'land', 'look', 'dance'}
needed |= {a for a, _, _ in behavior.TRICKS} | {v[0] for v in behavior.REACTION_ANIM.values() if v[0]}
check('every animation the behaviour can pick exists', needed <= set(frames), needed - set(frames))

print('\nALL PASS' if not fails else f'\n{fails} FAILED')
sys.exit(1 if fails else 0)
