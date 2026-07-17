# assets.py
#
# Fail-safe asset loaders. Everything here returns a usable widget (or None),
# never raises — so the app runs fine with the shipped placeholders and keeps
# working once real media is dropped into src/assets/.

import os
from gi.repository import Gtk, Gdk, GLib

# Resolve the assets directory whether running from the source tree
# (src/assets) or installed (pkgdatadir/ageverification/assets).
_HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(_HERE, "assets")


def asset_path(name):
    """Absolute path to an asset, or None if it doesn't exist.

    For SVG assets, prefer a same-named rasterized ``.png`` when one exists
    next to it. Some SVGs (notably Adobe Illustrator exports with CSS
    <style> blocks) render as an empty texture through Gtk.Image; a PNG copy
    sidesteps that reliably. Drop ``foo.png`` next to ``foo.svg`` to opt in.
    """
    if not name:
        return None
    if name.lower().endswith(".svg"):
        png = os.path.splitext(name)[0] + ".png"
        png_path = os.path.join(ASSETS_DIR, png)
        if os.path.exists(png_path):
            return png_path
    path = os.path.join(ASSETS_DIR, name)
    return path if os.path.exists(path) else None


def load_image(name, pixel_size=0):
    """Return a Gtk.Image for *name* (a filename in assets/), or None.

    Never raises. pixel_size>0 forces a square icon size.
    """
    path = asset_path(name)
    if not path:
        return None
    try:
        img = Gtk.Image.new_from_file(path)
        if pixel_size > 0:
            img.set_pixel_size(pixel_size)
        return img
    except Exception:
        return None


def load_paintable(name):
    """Return a Gdk.Texture (paintable) for *name*, or None."""
    path = asset_path(name)
    if not path:
        return None
    try:
        return Gdk.Texture.new_from_file(Gio_file(path))
    except Exception:
        return None


def Gio_file(path):
    # tiny indirection to avoid importing Gio at module top for one call
    from gi.repository import Gio
    return Gio.File.new_for_path(path)


def media_file(name):
    """Return a Gtk.MediaFile for *name* (e.g. subway_surfers.mp4), or None."""
    path = asset_path(name)
    if not path:
        return None
    try:
        return Gtk.MediaFile.new_for_file(Gio_file(path))
    except Exception:
        return None


# ---- sound -------------------------------------------------------------
# One-shot sound effects use a *direct GStreamer pipeline* (wavparse for WAV,
# mpegaudioparse+avdec_mp3 for MP3) instead of GtkMediaFile. GtkMediaFile
# routes everything through gstdecodebin3, which hits an assertion crash
# ("assertion failed: (collection)") when streams are created/played/destroyed
# rapidly (i.e. transition sounds). Direct pipelines bypass decodebin3.
#
# The looping background track uses GtkMediaFile (a single long-lived stream
# doesn't trigger the race).

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

_gst_inited = False


def _ensure_gst():
    global _gst_inited
    if not _gst_inited:
        Gst.init(None)
        _gst_inited = True


# Default assets. Override per-transition via the option's "transition.sound".
QUIZ_BACKGROUND_SOUND = "quiz-background.wav"
DEFAULT_TRANSITION_SOUND = "Tromba.mp3"


class GstSound:
    """A one-shot sound effect played via a direct GStreamer pipeline.

    Exposes a small GtkMediaStream-like API (set_muted, pause, set_playing,
    get_playing) so it's a drop-in replacement where the window code holds a
    reference to the current transition sound.
    """

    def __init__(self, pipeline):
        self._pipe = pipeline
        self._muted = False
        self._playing = False
        # Auto-cleanup when the stream ends.
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        self._bus_handler = bus.connect("message::eos", self._on_eos)

    def _on_eos(self, _bus, _msg):
        self._playing = False
        self._cleanup()

    def play(self):
        if self._pipe is None:
            return
        self._pipe.set_state(Gst.State.PLAYING)
        self._playing = True

    def set_playing(self, playing):
        if playing:
            self.play()
        else:
            self.pause()

    def get_playing(self):
        return self._playing

    def pause(self):
        if self._pipe is None:
            return
        self._pipe.set_state(Gst.State.PAUSED)
        self._playing = False

    def set_muted(self, muted):
        self._muted = muted
        # adjust volume on the volume element in the pipeline
        try:
            vol = self._pipe.get_by_name("vol") if self._pipe else None
            if vol is not None:
                vol.set_property("volume", 0.0 if muted else 1.0)
        except Exception:
            pass

    def get_muted(self):
        return self._muted

    def _cleanup(self):
        if self._pipe is None:
            return
        try:
            self._pipe.set_state(Gst.State.NULL)
            bus = self._pipe.get_bus()
            bus.disconnect(self._bus_handler)
            bus.remove_signal_watch()
        except Exception:
            pass
        self._pipe = None

    def stop(self):
        self._cleanup()


def _build_sound_pipeline(path):
    """Build a direct GStreamer pipeline for *path*, bypassing decodebin3."""
    _ensure_gst()
    ext = os.path.splitext(path)[1].lower()
    if ext == ".wav":
        decode = "wavparse"
    elif ext in (".mp3",):
        decode = "mpegaudioparse ! avdec_mp3"
    else:
        # Fall back to decodebin for unknown formats (rare).
        decode = "decodebin"
    desc = (f'filesrc location="{path}" ! {decode} ! '
            f'audioconvert ! audioresample ! '
            f'volume name=vol ! autoaudiosink name=audiosink')
    try:
        pipe = Gst.parse_launch(desc)
        return pipe
    except Exception:
        return None


def play_sound_once(name):
    """Play *name* as a one-shot sound effect. Returns a GstSound (or None).

    Uses a direct GStreamer pipeline (wavparse/mpegaudioparse) to avoid the
    gstdecodebin3 assertion crash that GtkMediaFile triggers.
    """
    path = asset_path(name)
    if not path:
        return None
    pipe = _build_sound_pipeline(path)
    if pipe is None:
        return None
    snd = GstSound(pipe)
    snd.play()
    return snd


# ---- background sound (GtkMediaFile, safe for single long-lived stream) --

def sound_stream(name, loop=False, volume=1.0):
    """Build a looping/playable GtkMediaFile stream for *name*, or None.

    Used for the background loop (a single long-lived stream that doesn't
    trigger the decodebin3 race). One-shot effects should use play_sound_once.
    """
    media = media_file(name)
    if media is None:
        return None
    try:
        media.set_loop(loop)
        media.set_muted(False)
        media.set_volume(volume)
    except Exception:
        pass
    return media
