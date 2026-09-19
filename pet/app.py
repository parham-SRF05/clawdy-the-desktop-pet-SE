"""The pet's window: draws the pixel art, moves it smoothly and handles the mouse."""
import os
import subprocess
import sys
import time
import tkinter as tk
import traceback

from . import chatter as talk, config, skins, sprites, winapi
from .behavior import Pet, walk_zone

KEY = '#ff00fe'            # see-through colour: clicks on it pass to the window below
FRAME_TIME = 1 / 60
AREA_EVERY, FULLSCREEN_EVERY, TOPMOST_EVERY = 2.0, 0.5, 1.0
WATCH_EVERY = 1.0          # how often it checks what you're doing
BUBBLE_ROOM = 64           # px above the pet for speech bubbles (two lines fit)
LOG_FILE = os.path.join(config.CONFIG_DIR, 'pet.log')

BG, BORDER, TEXT, MUTED = '#1f1e1d', '#d77757', '#f4f1ea', '#9b978f'
GREEN, ORANGE, RED, TRACK = '#8fce8a', '#e8906f', '#ff7a7a', '#3a3836'
STATE_LOOK = {'needs_you': ('Needs you', RED), 'working': ('Working', ORANGE),
              'done': ('Done', GREEN), 'idle': ('Idle', MUTED)}


def log(message):
    try:
        os.makedirs(config.CONFIG_DIR, exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M:%S  ') + message + '\n')
    except OSError:
        pass


def photo(master, rows):
    """A 1x PhotoImage from rows of colours (None = see-through)."""
    img = tk.PhotoImage(master=master, width=len(rows[0]), height=len(rows))
    img.put(' '.join('{' + ' '.join(c or KEY for c in row) + '}' for row in rows))
    return img


def scaled(master, img, scale, flip=False):
    out = tk.PhotoImage(master=master, width=img.width() * scale, height=img.height() * scale)
    out.tk.call(out, 'copy', img, '-zoom', scale, scale)
    if flip:
        mirrored = tk.PhotoImage(master=master, width=out.width(), height=out.height())
        mirrored.tk.call(mirrored, 'copy', out, '-subsample', -1, 1)
        return mirrored
    return out


def duration(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return '%ds' % seconds
    if seconds < 3600:
        return '%dm %02ds' % (seconds // 60, seconds % 60)
    return '%dh %02dm' % (seconds // 3600, seconds % 3600 // 60)


class App:
    def __init__(self, cfg):
        self.cfg = cfg
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.configure(bg=KEY)
        self.root.wm_attributes('-transparentcolor', KEY)
        self.root.wm_attributes('-topmost', True)

        self.frames, size = self._load_art()
        self.sprite_w, self.sprite_h = size
        self.canvas_w = self.sprite_w + 240
        self.canvas_h = self.sprite_h + BUBBLE_ROOM
        self.canvas = tk.Canvas(self.root, width=self.canvas_w, height=self.canvas_h, bg=KEY,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.sprite = self.canvas.create_image(self.canvas_w // 2, self.canvas_h, anchor='s')
        self.bubble_box = self.canvas.create_rectangle(0, 0, 0, 0, fill='#ffffff', outline='#3b2219',
                                                       width=2, state='hidden')
        self.bubble_text = self.canvas.create_text(0, 0, text='', fill='#3b2219', state='hidden', width=220,
                                                   anchor='s', justify='center', font=('Segoe UI', 9, 'bold'))
        self.shown_image = self.shown_bubble = self.shown_pos = None

        now = time.perf_counter()
        self.screen = winapi.walk_area()
        self.pet = Pet(cfg, self._zone(), size, now, screen=self.screen)
        self.chatter = talk.Chatter(cfg)
        self.pet.lines = self.chatter.line
        self.next_watch = now
        self.next_area = self.next_fullscreen = self.next_topmost = now
        self.hidden = False
        self.press = None
        self.dragging = False
        self.hover_off_at = None
        self.last = now

        self.root.geometry('%dx%d+%d+%d' % ((self.canvas_w, self.canvas_h) + self.pet.window_origin(
            self.canvas_w, self.canvas_h)))
        self.root.deiconify()
        self.root.update_idletasks()
        self.hwnd = winapi.top_level_handle(self.root)
        winapi.style_pet_window(self.hwnd)

        self.canvas.bind('<ButtonPress-1>', self._press)
        self.canvas.bind('<B1-Motion>', self._motion)
        self.canvas.bind('<ButtonRelease-1>', self._release)
        self.canvas.bind('<Button-3>', self._menu)
        self.canvas.bind('<Enter>', self._enter)
        self.canvas.bind('<Leave>', self._leave)
        self.root.after(1, self._tick)

    # --- art -------------------------------------------------------------------------------

    def _load_art(self):
        scale = self.cfg['scale']
        colors = {k: v for k, v in self.cfg['colors'].items() if k in sprites.DEFAULT_COLORS}
        built_in = sprites.build_frames(colors)
        skin, skin_size = {}, None
        try:
            skin, skin_size = skins.load(self.root, self.cfg['skin'])
        except (OSError, ValueError, tk.TclError) as e:
            log('Skin "%s" could not be loaded, using the built-in pet: %r' % (self.cfg['skin'], e))
        use_built_in = skin_size in (None, (sprites.W, sprites.H))
        frames = {}
        for name in set(built_in if use_built_in else ()) | set(skin):
            if name in skin:
                fps, images = skin[name]
            else:
                fps, images = sprites.fps(name), [photo(self.root, rows) for rows in built_in[name]]
            frames[name] = (fps, [scaled(self.root, i, scale) for i in images],
                            [scaled(self.root, i, scale, flip=True) for i in images])
        w, h = skin_size or (sprites.W, sprites.H)
        return frames, (w * scale, h * scale)

    def _zone(self):
        return walk_zone(self.screen, self.cfg['walk_width_percent'], self.cfg['walk_align'])

    # --- every frame -----------------------------------------------------------------------

    def _tick(self):
        start = time.perf_counter()
        try:
            self._step(start)
        except Exception:
            log('Error:\n' + traceback.format_exc())
        delay = FRAME_TIME - (time.perf_counter() - start)
        self.root.after(max(1, int(delay * 1000)), self._tick)

    def _step(self, now):
        dt, self.last = now - self.last, now
        if now >= self.next_area:
            self.next_area = now + AREA_EVERY
            self.screen = winapi.walk_area()
            self.pet.set_area(self._zone(), self.screen)
        if now >= self.next_fullscreen:
            self.next_fullscreen = now + FULLSCREEN_EVERY
            hide = self.cfg['hide_in_fullscreen'] and winapi.fullscreen_app_on_main_screen()
            if hide != self.hidden:
                self.hidden = hide
                winapi.show(self.hwnd, not hide)
                if hide:
                    self._hover_end()
        if now >= self.next_watch:
            self.next_watch = now + WATCH_EVERY
            self._watch_pc(now)
        self.pet.cursor = winapi.cursor_pos()
        if self.hover_off_at is not None and now >= self.hover_off_at:
            self._hover_end()
        self.pet.update(now, dt)
        if not self.hidden:
            self._draw(now)

    def _draw(self, now):
        pet = self.pet
        fps, right, left = self.frames.get(pet.anim) or self.frames['idle']
        images = right if pet.facing > 0 else left
        image = images[pet.frame(fps, len(images))]
        if image is not self.shown_image:
            self.canvas.itemconfigure(self.sprite, image=image)
            self.shown_image = image

        text = pet.bubble[0] if pet.bubble else None
        if text != self.shown_bubble:
            state = 'normal' if text else 'hidden'
            self.canvas.itemconfigure(self.bubble_box, state=state)
            self.canvas.itemconfigure(self.bubble_text, state=state)
            if text:  # (a hidden item has no size, so show it before measuring)
                cx, bottom = self.canvas_w // 2, BUBBLE_ROOM + self.sprite_h // 3
                self.canvas.itemconfigure(self.bubble_text, text=text)
                self.canvas.coords(self.bubble_text, cx, bottom - 8)
                box = self.canvas.bbox(self.bubble_text)
                if box:
                    x0, y0, x1, y1 = box
                    self.canvas.coords(self.bubble_box, x0 - 8, y0 - 4, x1 + 8, y1 + 4)
            self.shown_bubble = text

        pos = pet.window_origin(self.canvas_w, self.canvas_h)
        if pos != self.shown_pos or now >= self.next_topmost:
            self.next_topmost = now + TOPMOST_EVERY
            self.shown_pos = pos
            winapi.place(self.hwnd, *pos)

    def _watch_pc(self, now):
        """What you're doing: maybe something to say, and which animation to copy."""
        try:
            snap = talk.snapshot(winapi)
        except OSError:
            return
        for line in self.chatter.observe(time.time(), snap):
            self.pet.chat(now, line.text, line.anim)
        self.pet.hint = self.chatter.busy_with(snap) if self.cfg['copy_my_apps'] else None

    # --- hover: the pet notices the pointer ------------------------------------------------

    def _enter(self, event):
        self.hover_off_at = None
        if self.dragging:
            return
        self.pet.hover(time.perf_counter(), True)

    def _leave(self, event):
        self.hover_off_at = time.perf_counter() + 0.35  # small grace period: no flicker at the edges

    def _hover_end(self):
        self.hover_off_at = None
        self.pet.hover(time.perf_counter(), False)

    # --- mouse -----------------------------------------------------------------------------

    def _press(self, event):
        self.press = (event.x_root, event.y_root)
        self.dragging = False
        self.grab_offset = (self.pet.x - event.x_root, (self.pet.floor - self.pet.lift) - event.y_root)

    def _motion(self, event):
        if not self.press:
            return
        now = time.perf_counter()
        if not self.dragging and max(abs(event.x_root - self.press[0]), abs(event.y_root - self.press[1])) > 4:
            self.dragging = True
            self._hover_end()
            self.pet.grab(now, event.x_root + self.grab_offset[0], event.y_root + self.grab_offset[1])
        if self.dragging:
            self.pet.drag_to(event.x_root + self.grab_offset[0], event.y_root + self.grab_offset[1])

    def _release(self, event):
        now = time.perf_counter()
        if self.press and self.dragging:
            self.pet.release(now)
        elif self.press:
            self.pet.poke(now)
        self.press = None
        self.dragging = False

    def _menu(self, event):
        self._hover_end()
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label='Wake up' if self.pet.asleep else 'Go to sleep',
                         command=lambda: self.pet.toggle_sleep(time.perf_counter()))
        wander = tk.BooleanVar(self.root, self.cfg['wander'])
        tricks = tk.BooleanVar(self.root, self.cfg['tricks'])
        bubbles = tk.BooleanVar(self.root, self.cfg['bubbles'])
        menu.add_checkbutton(label='Walk around', variable=wander, command=lambda: self._set('wander', wander.get()))
        menu.add_checkbutton(label='Do tricks', variable=tricks, command=lambda: self._set('tricks', tricks.get()))
        chatty = tk.BooleanVar(self.root, self.cfg['chatter'])
        copy = tk.BooleanVar(self.root, self.cfg['copy_my_apps'])
        menu.add_checkbutton(label='Talk about what I do', variable=chatty,
                             command=lambda: self._set('chatter', chatty.get()))
        menu.add_checkbutton(label='Copy what I do', variable=copy,
                             command=lambda: self._set('copy_my_apps', copy.get()))
        menu.add_checkbutton(label='Speech bubbles', variable=bubbles,
                             command=lambda: self._set('bubbles', bubbles.get()))

        area = tk.Menu(menu, tearoff=0)
        width = tk.IntVar(self.root, self.cfg['walk_width_percent'])
        align = tk.StringVar(self.root, self.cfg['walk_align'])
        for percent in (25, 40, 60, 80, 100):
            area.add_radiobutton(label='%d%% of the taskbar' % percent, value=percent, variable=width,
                                 command=lambda p=percent: self._set_area('walk_width_percent', p))
        area.add_separator()
        for side in ('left', 'center', 'right'):
            area.add_radiobutton(label=side.capitalize(), value=side, variable=align,
                                 command=lambda s=side: self._set_area('walk_align', s))
        menu.add_cascade(label='Walking area', menu=area)

        sizes = tk.Menu(menu, tearoff=0)
        size = tk.IntVar(self.root, self.cfg['scale'])
        for scale in (1, 2, 3, 4):
            sizes.add_radiobutton(label='%dx' % scale, value=scale, variable=size,
                                  command=lambda s=scale: self._resize(s))
        menu.add_cascade(label='Size', menu=sizes)
        menu.add_separator()
        menu.add_command(label='Settings file...', command=self._open_settings)
        menu.add_command(label='Quit', command=self.quit)
        self._menu_ref = (menu, area, sizes, wander, tricks, chatty, copy, bubbles, width, align, size)  # keep alive
        menu.tk_popup(event.x_root, event.y_root)

    def _set(self, key, value):
        self.cfg[key] = value
        config.save(self.cfg)

    def _set_area(self, key, value):
        self._set(key, value)
        self.pet.set_area(self._zone(), self.screen)  # the pet walks over to its new area

    def _resize(self, scale):
        if scale != self.cfg['scale']:
            self._set('scale', scale)
            self.quit(restart=True)

    def _open_settings(self):
        config.save(self.cfg)
        os.startfile(config.CONFIG_FILE)

    def quit(self, restart=False):
        self.root.destroy()
        if restart:
            winapi.release_instance()
            subprocess.Popen([sys.executable] + sys.argv)

    def run(self):
        self.root.mainloop()


def main():
    winapi.make_dpi_aware()
    if not winapi.single_instance():
        return
    winapi.fine_timer(True)
    try:
        App(config.load()).run()
    except Exception:
        log('Crashed:\n' + traceback.format_exc())
        raise
    finally:
        winapi.fine_timer(False)
