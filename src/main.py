# main.py
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

import sys
import gi

from gettext import gettext as _

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Gio, Adw
from .window import AgeverificationWindow


class AgeverificationApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(application_id='moe.nyarchlinux.ageverification',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                         resource_base_path='/moe/nyarchlinux/ageverification')
        self.create_action('quit', lambda *_: self.quit(), ['<control>q'])
        self.create_action('about', self.on_about_action)
        self.create_action('restart', self.on_restart_action, ['<control>r'])
        self.create_action('shortcuts', self.on_shortcuts_action,
                           ['<control>question'])

    def do_activate(self):
        """Called when the application is activated.

        We raise the application's main window, creating it if
        necessary.
        """
        win = self.props.active_window
        if not win:
            win = AgeverificationWindow(application=self)
        win.present()

    def on_about_action(self, *args):
        """Callback for the app.about action."""
        about = Adw.AboutDialog(application_name='AgeVerification',
                                application_icon='moe.nyarchlinux.ageverification',
                                developer_name='Unknown',
                                version='0.1.0',
                                # Translators: Replace "translator-credits" with your name/username, and optionally an email or URL.
                                translator_credits = _('translator-credits'),
                                developers=['Unknown'],
                                copyright='© 2026 Unknown')
        about.present(self.props.active_window)

    def on_restart_action(self, *_):
        """Callback for the app.restart action — restart the test."""
        win = self.props.active_window
        if win is not None:
            win._on_start()

    def on_shortcuts_action(self, *_):
        """Callback for the app.shortcuts action."""
        win = self.props.active_window
        if win is None:
            return
        builder = Gtk.Builder.new_from_resource(
            '/moe/nyarchlinux/ageverification/shortcuts-dialog.ui')
        dlg = builder.get_object('shortcuts_dialog')
        if dlg is not None:
            dlg.set_transient_for(win)
            dlg.present()

    def create_action(self, name, callback, shortcuts=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main(version):
    """The application's entry point."""
    app = AgeverificationApplication()
    return app.run(sys.argv)
