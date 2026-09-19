# Clawdy — Solo Edition

A pixel-art desktop pet that lives on your Windows taskbar, walks around, does little tricks, and
talks about whatever you're doing.

![Clawdy's animations](docs/animations.png)

**No Claude Code needed.** This is the standalone edition: nothing to install, nothing to hook into,
no sessions to watch. Clawdy just lives on your taskbar and keeps itself busy.

---

## What it does

**It walks your taskbar.** Along the bottom of the screen, behind your windows, out of the way of
your clicks. It turns around at the edges, sits down sometimes, and gets on with its day.

**It never runs out of things to do.** Seventeen animations — typing, reading, thinking, running
commands, browsing, waving, dancing, celebrating — shuffled so you see every one of them before any
repeats. It doesn't stop when you stop.

**It notices what you're doing.** Open Chrome and it browses along. Open VS Code and it starts
typing. Open Steam, Spotify, a terminal, Task Manager — each one gets its own line:

> *Chrome! Say goodbye to your RAM.*
> *Ah, the terminal. Where the real work happens.*
> *Task Manager? Who are we investigating?*

It knows a few websites too, greets you when you come back from a break, notices when your battery
is low, and tells you to go to bed if you're still up at 3am. One line at a time, with a gap
between them, so it stays company rather than noise.

**It reacts to you.** Hover over it and it stops to look at you. Poke it three times quickly and it
gets dizzy. Drag it anywhere on screen and it falls back down to the taskbar. Move your mouse near
it and it turns to watch the pointer.

---

## Run it

Needs **Windows** and **Python 3.10+** — nothing else, no pip install.

```bash
python clawdy.pyw
```

Or double-click `clawdy.pyw`, which runs it without a console window. To start it with Windows, put
a shortcut to that file in:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

**Right-click the pet** for everything: sleep, walking area, size, which behaviours are on, and the
settings file.

---

## Make it yours

Settings live in `%USERPROFILE%\.clawdy\config.json`, written with defaults the first time it runs.

| Setting | Does what |
|---|---|
| `scale` | Size, in screen pixels per art pixel (1–8, default 2) |
| `walk_width_percent` | How much of the taskbar it walks on (10–100) |
| `walk_align` | Which part: `left`, `center`, `right` |
| `walk_speed` | 0.2 to 3.0 |
| `tricks` | The little animations while wandering |
| `chatter` | Whether it talks about what you're doing |
| `chatter_gap_seconds` | Minimum gap between lines (default 45) |
| `copy_my_apps` | Code along in VS Code, browse along in Chrome… |
| `custom_lines` | Your own jokes, e.g. `{"chrome": ["My own line"]}` |
| `sleep_after_seconds` | Fall asleep after this long idle (0 = never) |
| `hide_in_fullscreen` | Get out of the way of games and video |
| `colors` | Override any built-in colour, e.g. `{"body": "#6aa3ff"}` |
| `skin` | A folder in `%USERPROFILE%\.clawdy\skins` with your own PNGs |

Nothing here talks to the network, and nothing is stored beyond that settings file.

---

## How it's built

```
clawdy.pyw            double-click launcher
pet/
  app.py              the window: transparent, click-through, always on top, 60 fps
  behavior.py         walking, tricks, jumping, dragging, sleeping, talking (no window code)
  chatter.py          when to say something, and what you're busy with
  lines.py            every joke, and the app and website it belongs to
  sprites.py          the pixel art, drawn in code on a 48×32 grid
  winapi.py           taskbar position, the app in front, idle time, battery, single instance
  config.py           settings, validated on load
  skins.py            optional PNG skins
tests/
  test_logic.py       behaviour, settings, pixel art
  test_chatter.py     what it says and when
```

Run the tests with `python tests/test_logic.py` and `python tests/test_chatter.py`. Neither opens a
window.

**The window trick:** Tk with a colour-key transparent background, plus
`WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE` so it never steals focus or shows up in Alt-Tab. It reads the
real taskbar rectangle from `SHAppBarMessage`, so it sits correctly whether your taskbar is at the
bottom, centred, or auto-hiding.

---

## Credit

The character is the square one from Claude Code's welcome screen, redrawn here in pixel art.
If you *do* use Claude Code, the [full edition](https://github.com/parham-SRF05/clawdy-the-desktop-pet)
adds live reactions to what Claude is doing and a hover panel showing progress on your tasks.
