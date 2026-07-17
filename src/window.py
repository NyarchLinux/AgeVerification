
import random

from gi.repository import Adw, Gtk, Gdk, GLib

from . import assets
from .questions import (
    QUESTIONS,
    SUBWAY_SECS_PER_YEAR,
    SUBWAY_MAX_DISCOUNT,
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
    subway_flap = Gtk.Template.Child()
    subway_flap_content = Gtk.Template.Child()
    mute_button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # --- session state -------------------------------------------------
        self._q_index = 0            # current question index
        self._answers = []           # list of (age, weight) tuples
        self._subway_ms = 0          # accumulated Subway Surfers watch time (ms)
        self._subway_ticking = False
        self._subway_timeout_id = None
        self._media = None           # Gtk.MediaFile for the subway video (persistent)
        self._eval_timeout_ids = []  # running evaluation timers (for cleanup)
        self._bg_sound = None        # looping quiz background stream
        self._bg_sound_enabled = True
        self._transition_sound = None  # one-shot transition sound stream
        # Streams no longer in use but kept alive until their GStreamer pipeline
        # settles, to avoid spurious "g_object_unref: G_IS_OBJECT" warnings from
        # finalizing a still-realizing GtkMediaFile.
        self._gc_sounds = []
        self._muted = False            # global mute state (applies to all audio)

        # --- screens -------------------------------------------------------
        self._build_welcome()
        # quiz / transition / evaluation / result screens are built on demand

        # --- persistent Subway Surfers flap (wraps the whole stack) -------
        self._init_subway_flap()

        # mute/unmute toggle in the header bar
        self.mute_button.connect("toggled", self._on_mute_toggled)

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

    # ---- mute / unmute -------------------------------------------------
    def _on_mute_toggled(self, btn):
        self._muted = btn.get_active()
        btn.set_icon_name(
            "audio-volume-muted-symbolic" if self._muted
            else "audio-volume-high-symbolic")
        btn.set_tooltip_text(
            "Unmute" if self._muted else "Mute")
        self._apply_mute()

    def _apply_mute(self):
        """Apply the current mute state to every live audio stream."""
        for media in (self._bg_sound, self._transition_sound, self._media):
            if media is None:
                continue
            try:
                media.set_muted(self._muted)
            except Exception:
                pass

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
        self._cancel_eval_timers()
        self._stop_background_sound()
        self._stop_transition_sound()
        self._gc_sounds.clear()
        # hide the subway overlay on restart (keep the media stream alive)
        self._hide_subway()

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

        self._push(content_area, "quiz")
        self._start_background_sound()

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
            oimg = assets.load_image(opt["image"], pixel_size=128)
            if oimg is not None:
                inner.append(oimg)

        # Text is optional: an option may be image-only.
        opt_text = opt.get("text")
        if opt_text:
            text = Gtk.Label(label=opt_text)
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
        # Just the logo, no button chrome — still clickable to open the flap.
        btn = Gtk.Button()
        btn.set_has_frame(False)
        btn.set_tooltip_text("Watch some Subway Surfers")
        btn.set_valign(Gtk.Align.END)
        btn.set_halign(Gtk.Align.CENTER)

        logo = assets.load_image("subway-surfers-logo.svg", pixel_size=128)
        if logo is None:
            logo = Gtk.Image.new_from_icon_name(
                "media-playback-start-symbolic")
            logo.set_pixel_size(96)
        btn.set_child(logo)

        btn.connect("clicked", self._on_subway_clicked)
        return btn

    # ---- Subway Surfers persistent flap ---------------------------------
    # The flap wraps the entire GtkStack, so it's created once in the .ui and
    # persists across all screens (quiz, transition, etc.). Revealing the flap
    # shrinks the content to make room — nothing gets covered.

    def _init_subway_flap(self):
        """Populate the flap with the video widget and wire reveal changes."""
        frame = Gtk.AspectFrame.new(0.5, 0.5, 9.0 / 16.0, False)
        frame.set_size_request(253, 450)

        media = assets.media_file("subway_surfers.mp4")
        if media is not None:
            self._media = media
            media.set_loop(True)
            try:
                media.set_muted(self._muted)
            except Exception:
                pass
            try:
                media.set_volume(1.0)
            except Exception:
                pass
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

        self.subway_flap_content.append(frame)
        self.subway_flap.connect("notify::reveal-flap",
                                 self._on_flap_reveal_changed)

    def _on_subway_clicked(self, *_):
        """Toggle the Subway Surfers flap."""
        self.subway_flap.set_reveal_flap(
            not self.subway_flap.get_reveal_flap())

    def _on_flap_reveal_changed(self, _flap, _pspec):
        if self.subway_flap.get_reveal_flap():
            self._start_subway()
        else:
            self._stop_subway()

    def _show_subway(self):
        self.subway_flap.set_reveal_flap(True)

    def _hide_subway(self):
        self.subway_flap.set_reveal_flap(False)

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
        self._subway_timeout_id = GLib.timeout_add(1000, self._subway_tick)

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

    # ---- background + transition sound --------------------------------
    def _start_background_sound(self):
        """Start the looping quiz background track (if enabled & available)."""
        if not self._bg_sound_enabled:
            return
        if self._bg_sound is not None:
            return  # already playing
        media = assets.sound_stream(assets.QUIZ_BACKGROUND_SOUND,
                                    loop=True, volume=0.5)
        if media is None:
            return
        self._bg_sound = media
        try:
            media.set_muted(self._muted)
            media.play()
            media.set_playing(True)
        except Exception:
            pass

    def _stop_background_sound(self):
        """Stop and release the background track."""
        if self._bg_sound is not None:
            self._release_sound(self._bg_sound)
            self._bg_sound = None

    def _stop_transition_sound(self):
        if self._transition_sound is not None:
            snd = self._transition_sound
            self._transition_sound = None
            # GstSound (direct pipeline) needs explicit stop(); GtkMediaFile
            # uses the deferred-release path.
            if hasattr(snd, "stop"):
                snd.stop()
            else:
                self._release_sound(snd)

    def _release_sound(self, media):
        """Pause a stream and defer its release until the pipeline settles."""
        try:
            media.pause()
            media.set_playing(False)
        except Exception:
            pass
        # Keep a reference a little longer; clear it on the next idle tick so the
        # GStreamer backend finalizes cleanly instead of warning.
        self._gc_sounds.append(media)
        GLib.idle_add(self._gc_drain)

    def _gc_drain(self):
        # Drop one batch; keep it bounded so the list never grows unbounded.
        del self._gc_sounds[:]
        return GLib.SOURCE_REMOVE

    # ------------------------------------------------------------------ #
    # Answering + transitions (Spec 3)
    # ------------------------------------------------------------------ #
    def _on_answer(self, _btn, opt):
        self._answers.append((opt.get("age", 30), opt.get("weight", 1.0)))
        # The Subway Surfers overlay stays open if it was open — it floats
        # above all screens. Just stop the background loop.
        self._stop_background_sound()

        transition = opt.get("transition") or {}
        self._show_transition(
            transition.get("message", "..."),
            transition.get("image"),
            transition.get("sound"),
        )

    def _show_transition(self, message, image_name, sound_name=None):
        # Simple centered content. The Subway Surfers overlay (if open) floats
        # above independently — no need to embed it here.
        content = self._vbox(spacing=24, halign=Gtk.Align.CENTER,
                             valign=Gtk.Align.CENTER, margin=36)
        content.set_hexpand(True)

        if image_name:
            img = assets.load_image(image_name, pixel_size=180)
        else:
            img = None
        if img is None:
            img = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            img.set_pixel_size(96)
        content.append(img)

        lbl = Gtk.Label(label=message)
        lbl.set_wrap(True)
        lbl.set_justify(Gtk.Justification.CENTER)
        lbl.set_max_width_chars(50)
        lbl.add_css_class("title-2")
        content.append(lbl)

        # Optional sound: a per-transition clip if provided, else the default.
        self._stop_transition_sound()
        snd_name = sound_name or assets.DEFAULT_TRANSITION_SOUND
        self._transition_sound = assets.play_sound_once(snd_name)
        if self._transition_sound is not None and self._muted:
            try:
                self._transition_sound.set_muted(True)
            except Exception:
                pass

        self._push(content, "transition")

        GLib.timeout_add(TRANSITION_MS, self._after_transition)

    def _after_transition(self):
        self._stop_transition_sound()
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
        # hide subway overlay + stop all audio
        self._hide_subway()
        self._stop_background_sound()
        self._stop_transition_sound()

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

        # B. Subway Surfers discount: -1 year per SUBWAY_SECS_PER_YEAR seconds
        # watched (10s -> -1y, 20s -> -2y, ...), capped at SUBWAY_MAX_DISCOUNT.
        secs = self._subway_ms / 1000.0
        discount = min(SUBWAY_MAX_DISCOUNT, secs / SUBWAY_SECS_PER_YEAR)

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
        allowed = final >= 18

        box = self._vbox(spacing=18, halign=Gtk.Align.CENTER,
                         valign=Gtk.Align.CENTER, margin=36)

        # ---- verdict: large icon + status message ----------------------
        verdict_icon = Gtk.Image.new_from_icon_name(
            "object-select-symbolic" if allowed
            else "action-unavailable-symbolic")
        verdict_icon.set_pixel_size(96)
        # green check / red denied
        verdict_icon.add_css_class(
            "success" if allowed else "error")
        box.append(verdict_icon)

        verdict_title = Gtk.Label(
            label="You can use Nyarch now" if allowed
            else "You can't use the PC")
        verdict_title.add_css_class("title-1")
        box.append(verdict_title)

        verdict_sub = Gtk.Label(
            label="Age verified. Access granted." if allowed
            else "Come back when you're older.")
        verdict_sub.add_css_class("dim-label")
        box.append(verdict_sub)

        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # ---- age number + category -------------------------------------
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
