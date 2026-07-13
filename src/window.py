# window.py
#
# Copyright 2026 Unknown
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import math
import random

from gi.repository import Adw, Gtk, Gdk, GLib

from . import assets
from .questions import (
    QUESTIONS,
    SUBWAY_BREAKPOINT_SEC,
    SUBWAY_MAX_DISCOUNT,
    SUBWAY_CAP_SEC,
    EVAL_DURATION_SEC,
    EVAL_SUBTITLE_INTERVAL_SEC,
    EVAL_SUBTITLES,
    age_category,
)

# Transition screen dwell time (Spec 3: "3s").
TRANSITION_MS = 3000

LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H"]

# Age range sidebar: initial half-width of the band and how much it shrinks
# per answered question, so the estimate narrows during the quiz (Spec 3).
RANGE_INITIAL_HALF = 45
RANGE_SHRINK_PER_Q = 4
RANGE_MIN_HALF = 4


@Gtk.Template(resource_path="/moe/nyarchlinux/ageverification/window.ui")
class AgeverificationWindow(Adw.ApplicationWindow):
    __gtype_name__ = "AgeverificationWindow"

    stack = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # --- session state -------------------------------------------------
        self._q_index = 0            # current question index
        self._answers = []           # list of (age, weight) tuples
        self._subway_ms = 0          # accumulated Subway Surfers watch time (ms)
        self._subway_ticking = False
        self._subway_timeout_id = None
        self._media = None           # Gtk.MediaFile for the subway video
        self._flap = None
        self._eval_timeout_ids = []  # running evaluation timers (for cleanup)

        # --- screens -------------------------------------------------------
        self._build_welcome()
        # quiz / transition / evaluation / result screens are built on demand

        self.stack.set_visible_child_name("welcome")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _push(self, widget, name):
        """Add (if needed) and switch to a named page in the stack."""
        child = self.stack.get_child_by_name(name)
        if child is None:
            self.stack.add_named(widget, name)
        else:
            # replace existing page contents
            self.stack.remove(child)
            self.stack.add_named(widget, name)
        self.stack.set_visible_child_name(name)

    @staticmethod
    def _make_button(label_text="", css_classes=None, halign=Gtk.Align.FILL):
        btn = Gtk.Button(label=label_text, halign=halign)
        if css_classes:
            for c in css_classes:
                btn.add_css_class(c)
        return btn

    @staticmethod
    def _vbox(spacing=12, halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
              margin=0):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        box.set_halign(halign)
        box.set_valign(valign)
        if margin:
            box.set_margin_start(margin)
            box.set_margin_end(margin)
            box.set_margin_top(margin)
            box.set_margin_bottom(margin)
        return box

    # ------------------------------------------------------------------ #
    # Screen: Welcome (Spec 2)
    # ------------------------------------------------------------------ #
    def _build_welcome(self):
        box = self._vbox(spacing=24, halign=Gtk.Align.CENTER,
                         valign=Gtk.Align.CENTER, margin=36)

        logo = assets.load_image("nyarch-logo.svg", pixel_size=160)
        if logo is None:
            logo = Gtk.Image.new_from_icon_name(
                "applications-games-symbolic")
            logo.set_pixel_size(160)
        logo.add_css_class("welcome-logo")
        box.append(logo)

        title = Gtk.Label(label="Age Verification")
        title.add_css_class("title-1")
        box.append(title)

        subtitle = Gtk.Label(
            label="Answer a few highly scientific questions and let our\n"
                  "cutting-edge AI determine your true age.")
        subtitle.set_justify(Gtk.Justification.CENTER)
        subtitle.add_css_class("dim-label")
        subtitle.set_use_markup(True)
        box.append(subtitle)

        start_btn = Gtk.Button(label="Start Test")
        start_btn.add_css_class("suggested-action")
        start_btn.add_css_class("pill")
        start_btn.set_size_request(160, -1)
        start_btn.set_halign(Gtk.Align.CENTER)
        start_btn.connect("clicked", self._on_start)
        box.append(start_btn)

        self.stack.add_named(box, "welcome")

    def _on_start(self, *_):
        self._reset_state()
        self._show_question()

    def _reset_state(self):
        self._q_index = 0
        self._answers = []
        self._subway_ms = 0
        self._stop_subway_ticking()
        self._teardown_media()
        self._cancel_eval_timers()

    # ------------------------------------------------------------------ #
    # Screen: Quiz (Spec 3)
    # ------------------------------------------------------------------ #
    def _show_question(self):
        if self._q_index >= len(QUESTIONS):
            self._show_evaluation()
            return

        q = QUESTIONS[self._q_index]

        # ---- main horizontal layout (content + sidebar) ----------------
        content_area = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                               spacing=24)
        content_area.set_margin_start(24)
        content_area.set_margin_end(24)
        content_area.set_margin_top(12)
        content_area.set_margin_bottom(12)
        content_area.set_hexpand(True)
        content_area.set_vexpand(True)

        # left: the question + options
        left = self._vbox(spacing=18, halign=Gtk.Align.CENTER,
                          valign=Gtk.Align.CENTER)
        left.set_hexpand(True)

        # optional question image
        if q.get("image"):
            qimg = assets.load_image(q["image"], pixel_size=200)
            if qimg is not None:
                qimg.add_css_class("question-image")
                left.append(qimg)

        qtext = Gtk.Label(label=q["text"])
        qtext.set_wrap(True)
        qtext.set_justify(Gtk.Justification.CENTER)
        qtext.add_css_class("title-2")
        left.append(qtext)

        # options grid (2 columns)
        grid = Gtk.Grid()
        grid.set_row_spacing(12)
        grid.set_column_spacing(12)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_column_homogeneous(True)
        for i, opt in enumerate(q["options"][:4]):
            btn = self._build_option_button(i, opt)
            grid.attach(btn, i % 2, i // 2, 1, 1)
        left.append(grid)

        content_area.append(left)

        # right sidebar: age range + subway button
        sidebar = self._build_sidebar()
        content_area.append(sidebar)

        # ---- flap wrapping everything (Spec 3) -------------------------
        flap = Adw.Flap()
        flap.set_fold_policy(Adw.FlapFoldPolicy.NEVER)
        flap.set_flap_position(Gtk.PackType.END)   # reveal from the right
        flap.set_transition_type(Adw.FlapTransitionType.OVER)
        flap.set_locked(True)
        flap.set_modal(False)
        flap.set_content(content_area)
        flap.set_flap(self._build_subway_flap_content())
        flap.set_reveal_flap(False)

        # when reveal state changes, start/stop the video + ticking
        flap.connect("notify::reveal-flap", self._on_flap_reveal_changed)

        self._flap = flap
        self._push(flap, "quiz")

    # ---- option button -------------------------------------------------
    def _build_option_button(self, index, opt):
        letter = LETTERS[index] if index < len(LETTERS) else str(index + 1)
        btn = Gtk.Button()
        btn.set_size_request(220, -1)
        btn.add_css_class("option-button")
        btn.add_css_class("card")

        inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        inner.set_margin_start(12)
        inner.set_margin_end(12)
        inner.set_margin_top(10)
        inner.set_margin_bottom(10)

        letter_lbl = Gtk.Label(label=f"{letter})")
        letter_lbl.add_css_class("title-3")
        letter_lbl.set_xalign(0.0)
        inner.append(letter_lbl)

        if opt.get("image"):
            oimg = assets.load_image(opt["image"], pixel_size=48)
            if oimg is not None:
                inner.append(oimg)

        text = Gtk.Label(label=opt["text"])
        text.set_wrap(True)
        text.set_hexpand(True)
        text.set_xalign(0.0)
        inner.append(text)

        btn.set_child(inner)
        btn.connect("clicked", self._on_answer, opt)
        return btn

    # ---- right sidebar -------------------------------------------------
    def _build_sidebar(self):
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        sidebar.set_valign(Gtk.Align.FILL)
        sidebar.set_halign(Gtk.Align.FILL)
        sidebar.set_size_request(220, -1)
        sidebar.set_margin_top(12)
        sidebar.set_margin_bottom(12)

        # Top: estimated age range
        lo, hi = self._current_age_range()
        range_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        range_title = Gtk.Label(label="Estimated age")
        range_title.add_css_class("dim-label")
        range_title.add_css_class("caption")
        range_value = Gtk.Label(label=f"[{lo}–{hi}] yo")
        range_value.add_css_class("title-2")
        range_box.append(range_title)
        range_box.append(range_value)
        sidebar.append(range_box)

        # progress dots
        prog = Gtk.Label(label=f"Question {self._q_index + 1} / {len(QUESTIONS)}")
        prog.add_css_class("dim-label")
        prog.add_css_class("caption")
        sidebar.append(prog)

        # spacer pushes subway button to the bottom
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        sidebar.append(spacer)

        # Bottom: Subway Surfers button
        subway_btn = self._build_subway_button()
        sidebar.append(subway_btn)
        return sidebar

    def _build_subway_button(self):
        btn = Gtk.Button()
        btn.add_css_class("suggested-action")
        btn.add_css_class("pill")
        btn.set_tooltip_text("Watch some Subway Surfers")
        btn.set_valign(Gtk.Align.END)
        btn.set_halign(Gtk.Align.CENTER)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        logo = assets.load_image("subway-surfers-logo.svg", pixel_size=56)
        if logo is None:
            logo = Gtk.Image.new_from_icon_name(
                "media-playback-start-symbolic")
            logo.set_pixel_size(48)
        inner.append(logo)
        lbl = Gtk.Label(label="Subway Surfers")
        lbl.add_css_class("heading")
        inner.append(lbl)
        btn.set_child(inner)

        btn.connect("clicked", self._on_subway_clicked)
        return btn

    # ---- subway flap content (portrait video) -------------------------
    def _build_subway_flap_content(self):
        # portrait 9:16 container
        frame = Gtk.AspectFrame.new(0.5, 0.5, 9.0 / 16.0, False)
        frame.set_size_request(253, 450)  # ~9:16
        frame.set_halign(Gtk.Align.CENTER)
        frame.set_valign(Gtk.Align.CENTER)
        frame.set_margin_start(12)
        frame.set_margin_end(12)
        frame.set_margin_top(12)
        frame.set_margin_bottom(12)

        media = assets.media_file("subway_surfers.mp4")
        if media is not None:
            # Spec 3: no controls, with audio, looping.
            media.set_loop(True)
            try:
                media.set_muted(False)
            except Exception:
                pass
            try:
                media.set_volume(1.0)
            except Exception:
                pass
            self._media = media
            picture = Gtk.Picture()
            picture.set_paintable(media)
            picture.set_content_fit(Gtk.ContentFit.FILL)
            frame.set_child(picture)
        else:
            # placeholder when the video isn't shipped yet
            ph = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                         halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
            ph.add_css_class("osd")
            ph.set_size_request(253, 450)
            ic = Gtk.Image.new_from_icon_name("camera-video-symbolic")
            ic.set_pixel_size(64)
            ph.append(ic)
            msg = Gtk.Label(label="Drop subway_surfers.mp4\nin src/assets/")
            msg.add_css_class("title-4")
            ph.append(msg)
            frame.set_child(ph)
        return frame

    # ---- subway plumbing ----------------------------------------------
    def _on_subway_clicked(self, *_):
        if self._flap is None:
            return
        self._flap.set_reveal_flap(not self._flap.get_reveal_flap())

    def _on_flap_reveal_changed(self, flap, _pspec):
        revealed = flap.get_reveal_flap()
        if revealed:
            self._start_subway()
        else:
            self._stop_subway()

    def _start_subway(self):
        if self._media is not None:
            try:
                self._media.play()
                self._media.set_playing(True)
            except Exception:
                pass
        self._start_subway_ticking()

    def _stop_subway(self):
        if self._media is not None:
            try:
                self._media.pause()
                self._media.set_playing(False)
            except Exception:
                pass
        self._stop_subway_ticking()

    def _start_subway_ticking(self):
        if self._subway_ticking:
            return
        self._subway_ticking = True
        # tick every second, accumulate watch time
        self._subway_timeout_id = GLib.timeout_add(1000,
                                                   self._subway_tick)

    def _stop_subway_ticking(self):
        self._subway_ticking = False
        if self._subway_timeout_id is not None:
            GLib.source_remove(self._subway_timeout_id)
            self._subway_timeout_id = None

    def _subway_tick(self):
        if not self._subway_ticking:
            return GLib.SOURCE_REMOVE
        self._subway_ms += 1000
        return GLib.SOURCE_CONTINUE

    def _teardown_media(self):
        self._media = None
        self._flap = None

    # ------------------------------------------------------------------ #
    # Answering + transitions (Spec 3)
    # ------------------------------------------------------------------ #
    def _on_answer(self, _btn, opt):
        self._answers.append((opt.get("age", 30), opt.get("weight", 1.0)))
        # close subway if open before moving on
        if self._flap is not None and self._flap.get_reveal_flap():
            self._flap.set_reveal_flap(False)
        self._stop_subway()

        transition = opt.get("transition") or {}
        self._show_transition(
            transition.get("message", "..."),
            transition.get("image"),
        )

    def _show_transition(self, message, image_name):
        box = self._vbox(spacing=24, halign=Gtk.Align.CENTER,
                         valign=Gtk.Align.CENTER, margin=36)

        if image_name:
            img = assets.load_image(image_name, pixel_size=180)
        else:
            img = None
        if img is None:
            img = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            img.set_pixel_size(96)
        box.append(img)

        lbl = Gtk.Label(label=message)
        lbl.set_wrap(True)
        lbl.set_justify(Gtk.Justification.CENTER)
        lbl.set_max_width_chars(50)
        lbl.add_css_class("title-2")
        box.append(lbl)

        self._push(box, "transition")

        GLib.timeout_add(TRANSITION_MS, self._after_transition)

    def _after_transition(self):
        self._q_index += 1
        self._show_question()
        return GLib.SOURCE_REMOVE

    # ------------------------------------------------------------------ #
    # Running age range (Spec 3 right sidebar)
    # ------------------------------------------------------------------ #
    def _current_age_range(self):
        if not self._answers:
            half = RANGE_INITIAL_HALF
            return (max(0, 0), 0 + 2 * half)
        total_w = sum(w for _, w in self._answers)
        if total_w <= 0:
            mean = 30.0
        else:
            mean = sum(a * w for a, w in self._answers) / total_w
        answered = len(self._answers)
        total = len(QUESTIONS) or 1
        # band shrinks as more questions are answered
        half = max(RANGE_MIN_HALF,
                   RANGE_INITIAL_HALF - answered * RANGE_SHRINK_PER_Q)
        lo = max(0, int(round(mean - half)))
        hi = min(120, int(round(mean + half)))
        if hi < lo:
            lo, hi = hi, lo
        return (lo, hi)

    # ------------------------------------------------------------------ #
    # Screen: AI Evaluation (Spec 5)
    # ------------------------------------------------------------------ #
    def _show_evaluation(self):
        # make sure subway is fully stopped
        self._stop_subway()
        self._teardown_media()

        box = self._vbox(spacing=18, halign=Gtk.Align.CENTER,
                         valign=Gtk.Align.CENTER, margin=36)
        box.set_size_request(420, -1)

        # Adwaita-style animation on top
        spinner = Gtk.Spinner()
        spinner.set_size_request(72, 72)
        spinner.start()
        box.append(spinner)

        title = Gtk.Label(label="Using AI to evaluate your answers")
        title.add_css_class("title-2")
        box.append(title)

        subtitle = Gtk.Label(label=EVAL_SUBTITLES[0] if EVAL_SUBTITLES else "")
        subtitle.add_css_class("dim-label")
        subtitle.add_css_class("title-4")
        box.append(subtitle)

        progress = Gtk.ProgressBar()
        progress.set_fraction(0.0)
        progress.add_css_class("osd")
        box.append(progress)

        self._push(box, "evaluation")

        # animate progress bar over EVAL_DURATION_SEC (~10-15s)
        self._eval_start = GLib.get_monotonic_time()
        self._eval_end = self._eval_start + EVAL_DURATION_SEC * 1_000_000
        self._eval_progress = progress
        self._eval_subtitle = subtitle
        self._eval_seen = set()

        tick_id = GLib.timeout_add(50, self._eval_tick)
        sub_id = GLib.timeout_add(int(EVAL_SUBTITLE_INTERVAL_SEC * 1000),
                                   self._eval_rotate_subtitle)
        self._eval_timeout_ids.extend([tick_id, sub_id])

    def _eval_tick(self):
        now = GLib.get_monotonic_time()
        total = max(1, self._eval_end - self._eval_start)
        frac = (now - self._eval_start) / total
        frac = max(0.0, min(1.0, frac))
        self._eval_progress.set_fraction(frac)
        if frac >= 1.0:
            self._finish_evaluation()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _eval_rotate_subtitle(self):
        if not EVAL_SUBTITLES:
            return GLib.SOURCE_REMOVE
        # pick a random subtitle we haven't recently shown when possible
        remaining = [s for i, s in enumerate(EVAL_SUBTITLES)
                     if i not in self._eval_seen]
        if not remaining:
            self._eval_seen.clear()
            remaining = EVAL_SUBTITLES
        choice = random.choice(remaining)
        idx = EVAL_SUBTITLES.index(choice)
        self._eval_seen.add(idx)
        self._eval_subtitle.set_label(choice)
        return GLib.SOURCE_CONTINUE

    def _cancel_eval_timers(self):
        for tid in self._eval_timeout_ids:
            try:
                GLib.source_remove(tid)
            except Exception:
                pass
        self._eval_timeout_ids = []

    def _finish_evaluation(self):
        self._cancel_eval_timers()
        self._show_result()

    # ------------------------------------------------------------------ #
    # Final age math (Spec 6) + Result screen
    # ------------------------------------------------------------------ #
    def _compute_result(self):
        # A. weighted mean of ages
        total_w = sum(w for _, w in self._answers)
        if total_w <= 0:
            base_age = 30.0
        else:
            base_age = sum(a * w for a, w in self._answers) / total_w

        # B. Subway Surfers discount: logarithmic, up to 10y if > 2 min
        secs = self._subway_ms / 1000.0
        if secs <= SUBWAY_BREAKPOINT_SEC:
            discount = 0.0
        else:
            extra = secs - SUBWAY_BREAKPOINT_SEC
            denom = math.log(1 + (SUBWAY_CAP_SEC - SUBWAY_BREAKPOINT_SEC))
            discount = SUBWAY_MAX_DISCOUNT * math.log(1 + extra) / max(denom, 1e-9)
            discount = min(SUBWAY_MAX_DISCOUNT, max(0.0, discount))

        final = int(round(base_age - discount))
        final = max(0, min(120, final))

        return {
            "base_age": base_age,
            "discount": discount,
            "final": final,
            "subway_seconds": secs,
        }

    def _show_result(self):
        res = self._compute_result()
        final = res["final"]

        box = self._vbox(spacing=18, halign=Gtk.Align.CENTER,
                         valign=Gtk.Align.CENTER, margin=36)

        cat = Gtk.Label(label=age_category(final))
        cat.add_css_class("title-4")
        cat.add_css_class("dim-label")
        box.append(cat)

        big = Gtk.Label(label=str(final))
        big.set_use_markup(True)
        big.set_markup(f'<span size="x-large" weight="bold">{final}</span>')
        box.append(big)

        yrs = Gtk.Label(label="years old")
        yrs.add_css_class("dim-label")
        box.append(yrs)

        # breakdown
        breakdown_lines = [
            f"Base age (weighted answers): {res['base_age']:.1f}",
            f"Subway Surfers watched: {res['subway_seconds']:.0f}s "
            f"(−{res['discount']:.1f} years)",
        ]
        for line in breakdown_lines:
            b = Gtk.Label(label=line)
            b.add_css_class("dim-label")
            b.add_css_class("caption")
            box.append(b)

        # retake
        retake = Gtk.Button(label="Take the test again")
        retake.add_css_class("suggested-action")
        retake.add_css_class("pill")
        retake.set_halign(Gtk.Align.CENTER)
        retake.connect("clicked", self._on_start)
        box.append(retake)

        self._push(box, "result")
