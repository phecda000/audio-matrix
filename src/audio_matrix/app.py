from __future__ import annotations

import sys
from uuid import uuid4

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from audio_matrix import __version__  # noqa: E402
from audio_matrix.config import ConfigStore, OutputBusConfig  # noqa: E402
from audio_matrix.pulse import (  # noqa: E402
    VI_PREFIX,
    AudioMatrixController,
    BusRouteSpec,
    PulseAudio,
    PulseAudioError,
    Sink,
    SinkInput,
    Source,
)


APP_ID = "io.github.audiomatrix.AudioMatrix"
DIRECT_OUTPUT = "__direct_output__"

CSS = b"""
window, .app-shell {
    background-color: #F5F4F7;
    color: #1E2B27;
}
headerbar {
    background: #247C64;
    color: #F5F4F7;
    border-bottom: 1px solid #247C64;
    box-shadow: none;
}
headerbar .title {
    font-weight: 700;
    color: #F5F4F7;
}
headerbar .subtitle {
    color: #E4F2ED;
}
.page-title {
    font-size: 26px;
    font-weight: 800;
    color: #173E33;
}
.subtitle {
    color: #4D5F58;
    font-size: 14px;
}
.card {
    background: #FFFFFF;
    color: #1E2B27;
    border: 1px solid #D6DFDB;
    border-radius: 14px;
    padding: 14px;
}
.channel-left {
    border-top: 4px solid #2C9678;
}
.channel-right {
    border-top: 4px solid #64B69C;
}
.channel-letter {
    font-size: 28px;
    font-weight: 900;
    color: #2C9678;
}
.channel-left .channel-letter {
    color: #2C9678;
}
.channel-right .channel-letter {
    color: #4F9D85;
}
.channel-title {
    font-size: 18px;
    font-weight: 800;
    color: #1E2B27;
}
.section-title {
    font-size: 13px;
    font-weight: 800;
    color: #3E5D53;
}
.hint {
    color: #52645D;
    font-size: 13px;
}
.status-ok {
    color: #226D55;
}
.status-warn {
    color: #805B18;
}
.status-error {
    color: #A33D4C;
}
.status-bar {
    background: #FFFFFF;
    color: #25332E;
    border: 1px solid #D6DFDB;
    border-radius: 10px;
    padding: 10px 14px;
}
.route-button {
    font-weight: 800;
    padding: 10px 22px;
    background: #247C64;
    color: #FFFFFF;
    border-color: #216C58;
}
.mute-button:checked {
    background-color: #B6475A;
    color: #ffffff;
    border-color: #9A3A4B;
}
.dim-label {
    color: #486058;
}
.app-row {
    background: #F8FAF9;
    color: #1E2B27;
    border: 1px solid #D8E1DD;
    border-radius: 12px;
    padding: 12px;
}
.app-name {
    font-weight: 800;
    color: #1E2B27;
}
.bus-title {
    font-size: 20px;
    font-weight: 800;
    color: #1E2B27;
}
button {
    background-image: none;
    background-color: #E8EFEB;
    color: #1E2B27;
    border: 1px solid #C8D5CF;
    border-radius: 8px;
}
button:hover {
    background-color: #DDE9E4;
}
button.suggested-action, .route-button {
    background-color: #247C64;
    color: #FFFFFF;
    border-color: #216C58;
}
button.suggested-action:hover, .route-button:hover {
    background-color: #216C58;
}
entry {
    background-color: #FFFFFF;
    color: #1E2B27;
    border: 1px solid #BFCFC8;
    border-radius: 7px;
    padding: 5px 8px;
}
combobox button {
    background-color: #FFFFFF;
    color: #1E2B27;
    border: 1px solid #BFCFC8;
}
menuitem, checkbutton {
    color: #1E2B27;
}
menu {
    background-color: #FFFFFF;
}
menu menuitem:hover {
    background-color: #E7EEEA;
}
list {
    background-color: #FFFFFF;
    color: #1E2B27;
}
list row {
    color: #1E2B27;
    border-radius: 8px;
}
list row:selected {
    background-color: #DCEBE5;
    color: #1F6753;
}
switch {
    background-color: #C8D3CE;
    border-color: #AABBB3;
}
switch:checked {
    background-color: #2C9678;
}
switch slider {
    background-color: #FFFFFF;
}
scale trough {
    background-color: #D5E0DB;
}
scale highlight {
    background-color: #2C9678;
}
scale slider {
    background-color: #2C9678;
    border: 2px solid #F5F4F7;
}
notebook > header {
    background-color: #E7EEEA;
    border-color: #CFDAD5;
}
notebook > header > tabs > tab {
    color: #40554D;
    padding: 8px 18px;
}
notebook > header > tabs > tab:checked {
    background-color: #FFFFFF;
    color: #1F6753;
    border-bottom: 3px solid #2C9678;
}
"""


class SelectComboBox(Gtk.ComboBox):
    """Combo box with stable width and ellipsized labels."""

    def __init__(self, width_chars: int = 18):
        self.store = Gtk.ListStore(str, str)
        super().__init__(model=self.store)
        self.set_id_column(1)
        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        renderer.set_property("ellipsize-set", True)
        renderer.set_property("width-chars", width_chars)
        renderer.set_property("max-width-chars", width_chars)
        self.pack_start(renderer, True)
        self.add_attribute(renderer, "text", 0)
        self.set_popup_fixed_width(False)

    def append(self, item_id: str, label: str) -> None:
        self.store.append([label, item_id])

    def remove_all(self) -> None:
        self.store.clear()
        self.set_active(-1)

    def set_active_id(self, item_id: str) -> bool:
        for row in self.store:
            if row[1] == item_id:
                self.set_active_iter(row.iter)
                self.set_tooltip_text(row[0])
                return True
        self.set_active(-1)
        return False

    def get_active_id(self) -> str | None:
        active = self.get_active_iter()
        if active is None:
            return None
        return self.store[active][1]


class ChannelControls:
    def __init__(self, side: str, on_source_changed, on_volume_changed, on_mute_changed):
        self.side = side
        is_left = side == "left"
        title = "左声道" if is_left else "右声道"
        letter = "L" if is_left else "R"

        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.card.get_style_context().add_class("card")
        self.card.get_style_context().add_class("channel-left" if is_left else "channel-right")
        self.card.set_hexpand(True)

        heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        channel_letter = Gtk.Label(label=letter)
        channel_letter.get_style_context().add_class("channel-letter")
        channel_letter.set_xalign(0)
        heading.pack_start(channel_letter, False, False, 0)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title_label = Gtk.Label(label=title)
        title_label.get_style_context().add_class("channel-title")
        title_label.set_xalign(0)
        self.source_type_label = Gtk.Label(label="尚未选择来源")
        self.source_type_label.get_style_context().add_class("hint")
        self.source_type_label.set_xalign(0)
        title_box.pack_start(title_label, False, False, 0)
        title_box.pack_start(self.source_type_label, False, False, 0)
        heading.pack_start(title_box, True, True, 0)
        self.card.pack_start(heading, False, False, 0)

        source_label_widget = Gtk.Label(label="输出到这一侧的来源")
        source_label_widget.get_style_context().add_class("section-title")
        source_label_widget.set_xalign(0)
        self.card.pack_start(source_label_widget, False, False, 0)

        self.source_combo = SelectComboBox(18)
        self.source_combo.set_size_request(220, -1)
        self.source_combo.set_hexpand(True)
        self.source_combo.connect("changed", on_source_changed, side)
        self.card.pack_start(self.source_combo, False, False, 0)

        volume_heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        volume_label = Gtk.Label(label="通道音量")
        volume_label.get_style_context().add_class("section-title")
        volume_label.set_xalign(0)
        self.volume_value = Gtk.Label(label="100%")
        self.volume_value.get_style_context().add_class("dim-label")
        self.volume_value.set_xalign(1)
        volume_heading.pack_start(volume_label, True, True, 0)
        volume_heading.pack_end(self.volume_value, False, False, 0)
        self.card.pack_start(volume_heading, False, False, 0)

        self.volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.volume.set_draw_value(False)
        self.volume.connect("value-changed", on_volume_changed, side)
        self.card.pack_start(self.volume, False, False, 0)

        self.mute = Gtk.ToggleButton(label="静音这一侧")
        self.mute.get_style_context().add_class("mute-button")
        self.mute.connect("toggled", on_mute_changed, side)
        self.card.pack_start(self.mute, False, False, 0)

    def set_sources(self, sources: list[Source], selected: str) -> None:
        self.source_combo.remove_all()
        self.source_combo.append("", "不输出")
        for source in sources:
            self.source_combo.append(source.name, source_label(source))
        if not self.source_combo.set_active_id(selected):
            self.source_combo.set_active_id("")
        self.update_source_type(sources, selected)

    def update_source_type(self, sources: list[Source], source_name: str) -> None:
        source = next((item for item in sources if item.name == source_name), None)
        if source is None:
            self.source_type_label.set_text("不输出")
        elif source.name.startswith(VI_PREFIX):
            self.source_type_label.set_text("音频矩阵 · 虚拟输入")
        elif not source.monitor_of_sink:
            self.source_type_label.set_text("麦克风 / 硬件输入")
        else:
            self.source_type_label.set_text("系统或虚拟通道")


class MicSourceControls:
    def __init__(self, on_changed):
        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.card.get_style_context().add_class("card")

        title = Gtk.Label(label="麦克风输入")
        title.get_style_context().add_class("channel-title")
        title.set_xalign(0)
        self.card.pack_start(title, False, False, 0)

        hint = Gtk.Label(
            label="每条输出总线可以单独决定是否叠加麦克风、叠加到哪一侧以及监听音量。"
        )
        hint.get_style_context().add_class("hint")
        hint.set_xalign(0)
        hint.set_line_wrap(True)
        self.card.pack_start(hint, False, False, 0)

        self.source_combo = SelectComboBox(18)
        self.source_combo.set_size_request(200, -1)
        self.source_combo.set_hexpand(True)
        self.source_combo.connect("changed", on_changed)
        self.card.pack_start(self.source_combo, False, False, 0)

    def set_sources(self, sources: list[Source], selected: str) -> None:
        self.source_combo.remove_all()
        for source in sources:
            self.source_combo.append(source.name, source.description)
        target = selected
        if not target or not any(source.name == target for source in sources):
            target = sources[0].name if sources else ""
        if target:
            self.source_combo.set_active_id(target)


class OutputBusEditor:
    def __init__(
        self,
        bus: OutputBusConfig,
        on_change,
        sinks: list[Sink],
        sources: list[Source],
    ):
        self.bus = bus
        self.on_change = on_change
        self.sinks = sinks
        self.sources = sources
        self._loading = True

        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.card.set_margin_top(12)
        self.card.set_margin_bottom(12)
        self.card.set_margin_start(4)
        self.card.set_margin_end(4)

        identity = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name_title = Gtk.Label(label="总线名称")
        name_title.get_style_context().add_class("section-title")
        name_title.set_xalign(0)
        self.name_entry = Gtk.Entry()
        self.name_entry.set_text(bus.name)
        self.name_entry.set_width_chars(14)
        name_box.pack_start(name_title, False, False, 0)
        name_box.pack_start(self.name_entry, False, False, 0)
        identity.pack_start(name_box, False, False, 0)

        output_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        output_title = Gtk.Label(label="输出设备")
        output_title.get_style_context().add_class("section-title")
        output_title.set_xalign(0)
        self.output_combo = SelectComboBox(22)
        self.output_combo.set_size_request(250, -1)
        self.output_combo.set_hexpand(True)
        output_box.pack_start(output_title, False, False, 0)
        output_box.pack_start(self.output_combo, False, False, 0)
        identity.pack_start(output_box, True, True, 0)
        self.card.pack_start(identity, False, False, 0)

        channels = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        channels.set_homogeneous(True)
        self.left = ChannelControls(
            "left",
            self._on_source_changed,
            self._on_volume_changed,
            self._on_mute_changed,
        )
        self.right = ChannelControls(
            "right",
            self._on_source_changed,
            self._on_volume_changed,
            self._on_mute_changed,
        )
        channels.pack_start(self.left.card, True, True, 0)
        channels.pack_start(self.right.card, True, True, 0)
        self.card.pack_start(channels, False, False, 0)

        mic_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        mic_card.get_style_context().add_class("card")
        mic_heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        mic_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        mic_title = Gtk.Label(label="本条总线的麦克风叠加")
        mic_title.get_style_context().add_class("channel-title")
        mic_title.set_xalign(0)
        mic_hint = Gtk.Label(label="叠加在左右声道来源之外，不占用矩阵来源位置。")
        mic_hint.get_style_context().add_class("hint")
        mic_hint.set_xalign(0)
        mic_text.pack_start(mic_title, False, False, 0)
        mic_text.pack_start(mic_hint, False, False, 0)
        mic_heading.pack_start(mic_text, True, True, 0)
        self.mic_enable = Gtk.Switch()
        mic_heading.pack_end(self.mic_enable, False, False, 0)
        mic_card.pack_start(mic_heading, False, False, 0)

        options = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        self.mic_left = Gtk.CheckButton(label="叠加到左声道")
        self.mic_right = Gtk.CheckButton(label="叠加到右声道")
        options.pack_start(self.mic_left, False, False, 0)
        options.pack_start(self.mic_right, False, False, 0)
        mic_card.pack_start(options, False, False, 0)

        volume_heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        volume_label = Gtk.Label(label="麦克风监听音量")
        volume_label.get_style_context().add_class("section-title")
        volume_label.set_xalign(0)
        self.mic_volume_value = Gtk.Label(label="100%")
        self.mic_volume_value.get_style_context().add_class("dim-label")
        volume_heading.pack_start(volume_label, True, True, 0)
        volume_heading.pack_end(self.mic_volume_value, False, False, 0)
        mic_card.pack_start(volume_heading, False, False, 0)
        self.mic_volume = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        self.mic_volume.set_draw_value(False)
        mic_card.pack_start(self.mic_volume, False, False, 0)
        self.card.pack_start(mic_card, False, False, 0)

        self.set_devices(sinks, sources)
        self.left.volume.set_value(bus.left_volume)
        self.right.volume.set_value(bus.right_volume)
        self.left.volume_value.set_text(f"{bus.left_volume}%")
        self.right.volume_value.set_text(f"{bus.right_volume}%")
        self.left.mute.set_active(bus.left_muted)
        self.right.mute.set_active(bus.right_muted)
        self.mic_enable.set_active(bus.mic_enabled)
        self.mic_left.set_active(bus.mic_left_enabled)
        self.mic_right.set_active(bus.mic_right_enabled)
        self.mic_volume.set_value(bus.mic_volume)
        self.mic_volume_value.set_text(f"{bus.mic_volume}%")

        self.name_entry.connect("changed", self._on_name_changed)
        self.output_combo.connect("changed", self._on_output_changed)
        self.mic_enable.connect("notify::active", self._on_mic_settings_changed)
        self.mic_left.connect("toggled", self._on_mic_settings_changed)
        self.mic_right.connect("toggled", self._on_mic_settings_changed)
        self.mic_volume.connect("value-changed", self._on_mic_volume_changed)
        self._loading = False
        self.card.show_all()

    def set_devices(self, sinks: list[Sink], sources: list[Source]) -> None:
        self._loading = True
        self.sinks = sinks
        self.sources = sources
        self.output_combo.remove_all()
        for sink in sinks:
            self.output_combo.append(sink.name, sink.description)
        if not self.output_combo.set_active_id(self.bus.output_sink) and sinks:
            self.output_combo.set_active(0)

        self.left.set_sources(sources, self.bus.left_source)
        self.right.set_sources(sources, self.bus.right_source)
        self._loading = False

    def _on_name_changed(self, entry: Gtk.Entry) -> None:
        if self._loading:
            return
        name = entry.get_text().strip()
        if not name:
            return
        self.bus.name = name
        self.on_change(self.bus, "name")

    def _on_output_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self._loading:
            return
        sink = combo.get_active_id()
        if sink is None:
            return
        self.bus.output_sink = sink
        self.on_change(self.bus, "restart")

    def _on_source_changed(self, combo: Gtk.ComboBoxText, side: str) -> None:
        if self._loading:
            return
        source = combo.get_active_id()
        if source is None:
            return
        controls = self.left if side == "left" else self.right
        if side == "left":
            self.bus.left_source = source
        else:
            self.bus.right_source = source
        controls.update_source_type(self.sources, source)
        self.on_change(self.bus, "restart")

    def _on_volume_changed(self, scale: Gtk.Scale, side: str) -> None:
        if self._loading:
            return
        volume = int(round(scale.get_value()))
        controls = self.left if side == "left" else self.right
        controls.volume_value.set_text(f"{volume}%")
        if side == "left":
            self.bus.left_volume = volume
            action = "left_volume"
        else:
            self.bus.right_volume = volume
            action = "right_volume"
        self.on_change(self.bus, action)

    def _on_mute_changed(self, button: Gtk.ToggleButton, side: str) -> None:
        if self._loading:
            return
        muted = button.get_active()
        button.set_label("已静音" if muted else "静音这一侧")
        if side == "left":
            self.bus.left_muted = muted
            action = "left_mute"
        else:
            self.bus.right_muted = muted
            action = "right_mute"
        self.on_change(self.bus, action)

    def _on_mic_settings_changed(self, *_args) -> None:
        if self._loading:
            return
        self.bus.mic_enabled = self.mic_enable.get_active()
        self.bus.mic_left_enabled = self.mic_left.get_active()
        self.bus.mic_right_enabled = self.mic_right.get_active()
        self.on_change(self.bus, "restart")

    def _on_mic_volume_changed(self, scale: Gtk.Scale) -> None:
        if self._loading:
            return
        volume = int(round(scale.get_value()))
        self.bus.mic_volume = volume
        self.mic_volume_value.set_text(f"{volume}%")
        self.on_change(self.bus, "mic_volume")


class ApplicationRow:
    def __init__(
        self,
        stream: SinkInput,
        virtual_sinks: list[Sink],
        direct_sink: Sink | None,
        selected_target: str,
        on_target_changed,
        on_volume_changed,
        on_mute_changed,
    ):
        self.stream = stream
        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.card.get_style_context().add_class("app-row")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        name = Gtk.Label(label=stream.label)
        name.get_style_context().add_class("app-name")
        name.set_xalign(0)
        name.set_hexpand(True)
        name.set_ellipsize(3)
        media = Gtk.Label(label=stream.media_name or "正在播放的音频流")
        media.get_style_context().add_class("hint")
        media.set_xalign(0)
        media.set_ellipsize(3)
        text.pack_start(name, False, False, 0)
        text.pack_start(media, False, False, 0)
        header.pack_start(text, True, True, 0)

        self.mute = Gtk.ToggleButton(label="静音")
        self.mute.get_style_context().add_class("mute-button")
        self.mute.set_active(stream.muted)
        self.mute.connect(
            "toggled", lambda button: on_mute_changed(stream, button.get_active())
        )
        header.pack_end(self.mute, False, False, 0)
        self.card.pack_start(header, False, False, 0)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.target_combo = SelectComboBox(18)
        self.target_combo.set_size_request(200, -1)
        self.target_combo.append("", "保持当前输出")
        for index, sink in enumerate(virtual_sinks, 1):
            self.target_combo.append(sink.name, f"音频矩阵 · 输入 {index}")
        if direct_sink is not None:
            self.target_combo.append(DIRECT_OUTPUT, "直接送到总线 1 输出")
        self.target_combo.set_hexpand(True)
        if selected_target:
            self.target_combo.set_active_id(selected_target)
        else:
            self.target_combo.set_active_id("")
        self.target_combo.connect(
            "changed", lambda combo: on_target_changed(stream, combo.get_active_id() or "")
        )
        controls.pack_start(self.target_combo, True, True, 0)

        self.volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.volume.set_draw_value(False)
        self.volume.set_size_request(105, -1)
        self.volume.set_value(stream.volume)
        self.volume.connect(
            "value-changed", lambda scale: on_volume_changed(stream, int(scale.get_value()))
        )
        controls.pack_start(self.volume, False, False, 0)
        self.card.pack_start(controls, False, False, 0)
        self.card.show_all()


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, application: Gtk.Application):
        super().__init__(application=application, title="音频矩阵")
        self.set_default_size(1480, 925)
        self.set_size_request(1480, 925)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.config_store = ConfigStore()
        self.config = self.config_store.load()
        self.pulse = PulseAudio()
        self.controller = AudioMatrixController(self.pulse)
        self.sinks: list[Sink] = []
        self.sources: list[Source] = []
        self.bus_editors: dict[str, OutputBusEditor] = {}
        self.bus_rows: dict[str, Gtk.ListBoxRow] = {}
        self.bus_row_labels: dict[str, tuple[Gtk.Label, Gtk.Label]] = {}
        self._engine_ready = False
        self._loading = True
        self._restart_pending = False
        self._save_pending = False
        self._volume_timers: dict[tuple[str, str], int] = {}
        self._health_timer = 0
        self._app_signature: tuple = ()
        self._apps_loading = False

        self._install_css()
        self._build_ui()
        self.connect("destroy", self._on_destroy)
        self._loading = False
        self.refresh_all()
        self._health_timer = GLib.timeout_add_seconds(2, self._periodic_tick)

        if self.config.auto_start:
            GLib.timeout_add(400, self._auto_start)

    def _install_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        screen = Gdk.Screen.get_default()
        if screen is not None:
            Gtk.StyleContext.add_provider_for_screen(
                screen,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _build_ui(self) -> None:
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("音频矩阵")
        header.set_subtitle(f"多总线混音 · 麦克风与应用路由 · v{__version__}")
        self.set_titlebar(header)

        refresh_button = Gtk.Button(label="刷新设备")
        refresh_button.connect("clicked", lambda _button: self.refresh_all())
        header.pack_end(refresh_button)

        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        shell.get_style_context().add_class("app-shell")
        shell.set_margin_top(16)
        shell.set_margin_bottom(16)
        shell.set_margin_start(18)
        shell.set_margin_end(18)
        self.add(shell)

        heading_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        title = Gtk.Label(label="音频矩阵")
        title.get_style_context().add_class("page-title")
        title.set_xalign(0)
        subtitle = Gtk.Label(
            label="每条总线独立选择声卡、左右声道来源和麦克风监听"
        )
        subtitle.get_style_context().add_class("subtitle")
        subtitle.set_xalign(0)
        title_box.pack_start(title, False, False, 0)
        title_box.pack_start(subtitle, False, False, 0)
        heading_row.pack_start(title_box, True, True, 0)
        shell.pack_start(heading_row, False, False, 0)

        self.compat_warning = Gtk.Label(
            label="检测到 Pulsemeeter 仍在运行。请关闭 Pulsemeeter，避免两套虚拟设备争抢应用音频。"
        )
        self.compat_warning.get_style_context().add_class("status-bar")
        self.compat_warning.get_style_context().add_class("status-warn")
        self.compat_warning.set_xalign(0)
        self.compat_warning.set_line_wrap(True)
        self.compat_warning.set_no_show_all(True)
        shell.pack_start(self.compat_warning, False, False, 0)

        workspace = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        workspace.set_vexpand(True)
        shell.pack_start(workspace, True, True, 0)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sidebar.set_size_request(225, -1)
        bus_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        bus_card.get_style_context().add_class("card")
        bus_title = Gtk.Label(label="输出总线")
        bus_title.get_style_context().add_class("channel-title")
        bus_title.set_xalign(0)
        bus_card.pack_start(bus_title, False, False, 0)

        self.bus_list = Gtk.ListBox()
        self.bus_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.bus_list.connect("row-selected", self._on_bus_row_selected)
        bus_scroll = Gtk.ScrolledWindow()
        bus_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.EXTERNAL)
        bus_scroll.set_min_content_height(250)
        bus_scroll.add(self.bus_list)
        bus_card.pack_start(bus_scroll, True, True, 0)

        bus_toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        add_bus = Gtk.Button(label="＋ 新建总线")
        add_bus.connect("clicked", self._add_bus)
        bus_toolbar.pack_start(add_bus, True, True, 0)
        remove_bus = Gtk.Button(label="删除当前总线")
        remove_bus.connect("clicked", self._remove_current_bus)
        bus_toolbar.pack_start(remove_bus, True, True, 0)
        bus_card.pack_start(bus_toolbar, False, False, 0)
        sidebar.pack_start(bus_card, True, True, 0)

        self.mic = MicSourceControls(self._on_mic_source_changed)
        sidebar.pack_start(self.mic.card, False, False, 0)
        workspace.pack_start(sidebar, False, False, 0)

        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        center.set_hexpand(True)
        self.bus_stack = Gtk.Stack()
        self.bus_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.bus_stack.set_transition_duration(120)
        center.pack_start(self.bus_stack, True, True, 0)
        workspace.pack_start(center, True, True, 0)

        apps_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        apps_card.get_style_context().add_class("card")
        apps_card.set_size_request(350, -1)
        apps_heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        apps_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        apps_title = Gtk.Label(label="应用分流")
        apps_title.get_style_context().add_class("channel-title")
        apps_title.set_xalign(0)
        apps_hint = Gtk.Label(
            label="把应用送到输入 1–3，再由各条总线选择。"
        )
        apps_hint.get_style_context().add_class("hint")
        apps_hint.set_xalign(0)
        apps_hint.set_line_wrap(True)
        apps_text.pack_start(apps_title, False, False, 0)
        apps_text.pack_start(apps_hint, False, False, 0)
        apps_heading.pack_start(apps_text, True, True, 0)
        refresh_apps = Gtk.Button(label="刷新应用")
        refresh_apps.connect("clicked", lambda _button: self._refresh_applications(force=True))
        apps_heading.pack_end(refresh_apps, False, False, 0)
        apps_card.pack_start(apps_heading, False, False, 0)

        self.apps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        apps_scroll = Gtk.ScrolledWindow()
        apps_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.EXTERNAL)
        apps_scroll.add(self.apps_box)
        apps_card.pack_start(apps_scroll, True, True, 0)
        workspace.pack_start(apps_card, False, False, 0)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.route_button = Gtk.Button(label="启动所有总线")
        self.route_button.get_style_context().add_class("suggested-action")
        self.route_button.get_style_context().add_class("route-button")
        self.route_button.connect("clicked", self._start_routing)
        controls.pack_start(self.route_button, True, True, 0)

        self.stop_button = Gtk.Button(label="停止输出")
        self.stop_button.connect("clicked", self._stop_routing)
        self.stop_button.set_sensitive(False)
        controls.pack_start(self.stop_button, False, False, 0)

        self.auto_start = Gtk.CheckButton(label="打开应用时自动连接")
        self.auto_start.set_active(self.config.auto_start)
        self.auto_start.connect("toggled", self._on_auto_start_changed)
        controls.pack_end(self.auto_start, False, False, 0)
        shell.pack_start(controls, False, False, 0)

        self.status_label = Gtk.Label(label="正在启动音频矩阵…")
        self.status_label.get_style_context().add_class("status-bar")
        self.status_label.set_xalign(0)
        self.status_label.set_line_wrap(True)
        shell.pack_start(self.status_label, False, False, 0)

    def _set_status(self, message: str, kind: str = "") -> None:
        context = self.status_label.get_style_context()
        for css_class in ("status-ok", "status-warn", "status-error"):
            context.remove_class(css_class)
        if kind:
            context.add_class(f"status-{kind}")
        self.status_label.set_text(message)

    def refresh_all(self) -> None:
        if self._loading:
            return
        try:
            if not self.pulse.available():
                raise PulseAudioError("PulseAudio 没有运行。")
            if not self._engine_ready:
                self.controller.cleanup_stale_pulsemeeter()
                self.controller.cleanup_routes()
                self.controller.ensure_engine()
                self._engine_ready = True
            raw_sinks = self.pulse.sinks()
            raw_sources = self.pulse.sources()
        except PulseAudioError as error:
            self._engine_ready = False
            self._set_status(f"启动音频引擎失败：{error}", "error")
            return

        self.sinks = self._available_sinks(raw_sinks)
        self.sources = self._available_sources(raw_sources)

        self._loading = True
        try:
            if not self.config.buses:
                self.config.buses = [OutputBusConfig()]
            self._normalize_bus_devices()
            hardware_sources = [source for source in self.sources if not source.monitor_of_sink]
            mic_names = {source.name for source in hardware_sources}
            if self.config.mic_source not in mic_names:
                self.config.mic_source = hardware_sources[0].name if hardware_sources else ""
            self.mic.set_sources(hardware_sources, self.config.mic_source)

            if not self.bus_editors:
                for bus in self.config.buses:
                    self._append_bus_editor(bus, select=False)
            else:
                for bus in self.config.buses:
                    editor = self.bus_editors.get(bus.id)
                    if editor is not None:
                        editor.set_devices(self.sinks, self.sources)
                        self._update_bus_row(bus)
        finally:
            self._loading = False
            self._save_config()

        self._refresh_applications(force=True)
        self._update_warnings()
        self._set_status(
            f"音频引擎已就绪：{len(self.config.buses)} 条独立输出总线，"
            f"{len(self.sinks)} 个物理输出设备。",
            "ok",
        )

    def _normalize_bus_devices(self) -> None:
        sink_names = {sink.name for sink in self.sinks}
        source_names = {source.name for source in self.sources}
        default_sink = self.sinks[0].name if self.sinks else ""
        left_default = self._virtual_source_name(1)
        right_default = self._virtual_source_name(2)
        for bus in self.config.buses:
            if bus.output_sink not in sink_names:
                bus.output_sink = default_sink
            if bus.left_source not in source_names:
                bus.left_source = left_default
            if bus.right_source not in source_names:
                bus.right_source = right_default

    def _append_bus_editor(self, bus: OutputBusConfig, select: bool = True) -> None:
        editor = OutputBusEditor(
            bus,
            self._on_bus_changed,
            self.sinks,
            self.sources,
        )
        self.bus_editors[bus.id] = editor
        self.bus_stack.add_named(editor.card, bus.id)

        row = Gtk.ListBoxRow()
        row.bus_id = bus.id
        row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        row_box.set_margin_top(7)
        row_box.set_margin_bottom(7)
        row_box.set_margin_start(8)
        row_box.set_margin_end(8)
        name_label = Gtk.Label(label=bus.name)
        name_label.get_style_context().add_class("app-name")
        name_label.set_xalign(0)
        output_label = Gtk.Label(label=self._sink_description(bus.output_sink))
        output_label.get_style_context().add_class("hint")
        output_label.set_xalign(0)
        output_label.set_ellipsize(3)
        row_box.pack_start(name_label, False, False, 0)
        row_box.pack_start(output_label, False, False, 0)
        row.add(row_box)
        row.show_all()
        self.bus_list.add(row)
        self.bus_rows[bus.id] = row
        self.bus_row_labels[bus.id] = (name_label, output_label)

        if select:
            self.bus_list.select_row(row)
        elif not self.bus_list.get_selected_row():
            self.bus_list.select_row(row)
        self.bus_stack.set_visible_child_name(bus.id)
        editor.card.show_all()

    def _sink_description(self, sink_name: str) -> str:
        sink = next((item for item in self.sinks if item.name == sink_name), None)
        return sink.description if sink is not None else "未选择输出设备"

    def _update_bus_row(self, bus: OutputBusConfig) -> None:
        labels = self.bus_row_labels.get(bus.id)
        if labels is None:
            return
        labels[0].set_text(bus.name)
        labels[1].set_text(self._sink_description(bus.output_sink))

    def _on_bus_row_selected(
        self, _list_box: Gtk.ListBox, row: Gtk.ListBoxRow | None
    ) -> None:
        if row is None:
            return
        bus_id = getattr(row, "bus_id", "")
        if bus_id in self.bus_editors:
            self.bus_stack.set_visible_child_name(bus_id)

    def _add_bus(self, _button: Gtk.Button) -> None:
        number = len(self.config.buses) + 1
        used_names = {bus.name for bus in self.config.buses}
        while f"总线 {number}" in used_names:
            number += 1
        bus = OutputBusConfig(
            id=f"bus_{uuid4().hex[:8]}",
            name=f"总线 {number}",
            output_sink=self.sinks[0].name if self.sinks else "",
            left_source=self._virtual_source_name(1),
            right_source=self._virtual_source_name(2),
            mic_enabled=False,
        )
        self.config.buses.append(bus)
        self._append_bus_editor(bus)
        self._save_config()
        self._set_status(f"已新建 {bus.name}。", "ok")
        self._schedule_restart()

    def _remove_current_bus(self, _button: Gtk.Button) -> None:
        if len(self.config.buses) <= 1:
            self._show_error("不能删除总线", "至少需要保留一条输出总线。")
            return
        bus_id = self._current_bus_id()
        editor = self.bus_editors.get(bus_id)
        if editor is None:
            return
        self.config.buses = [bus for bus in self.config.buses if bus.id != bus_id]
        self.bus_stack.remove(editor.card)
        row = self.bus_rows.pop(bus_id, None)
        if row is not None:
            self.bus_list.remove(row)
        self.bus_editors.pop(bus_id, None)
        self.bus_row_labels.pop(bus_id, None)
        if self.bus_rows:
            self.bus_list.select_row(next(iter(self.bus_rows.values())))
        self._save_config()
        self._set_status("已删除当前输出总线。", "ok")
        self._schedule_restart()

    def _current_bus_id(self) -> str:
        row = self.bus_list.get_selected_row()
        if row is not None:
            return getattr(row, "bus_id", self.config.buses[0].id)
        return self.config.buses[0].id

    def _on_bus_changed(self, bus: OutputBusConfig, action: str) -> None:
        if action == "name":
            self._update_bus_row(bus)
            self._save_config()
            return
        if action == "restart":
            self._update_bus_row(bus)
        if action in {"left_volume", "right_volume", "mic_volume"}:
            self._apply_bus_volume_live(bus, action)
        elif action in {"left_mute", "right_mute"}:
            side = action.removesuffix("_mute")
            if self.controller.running:
                try:
                    self.controller.set_bus_channel_mute(
                        bus.id, side, getattr(bus, action)
                    )
                except PulseAudioError as error:
                    self._set_status(f"设置静音失败：{error}", "error")
        elif action == "restart":
            self._schedule_restart()
        self._save_config()

    def _apply_bus_volume_live(self, bus: OutputBusConfig, action: str) -> None:
        if not self.controller.running:
            return
        key = (bus.id, action)
        previous = self._volume_timers.pop(key, None)
        if previous:
            GLib.source_remove(previous)
        self._volume_timers[key] = GLib.timeout_add(
            80, self._apply_bus_volume_now, bus.id, action
        )

    def _apply_bus_volume_now(self, bus_id: str, action: str) -> bool:
        self._volume_timers.pop((bus_id, action), None)
        bus = next((item for item in self.config.buses if item.id == bus_id), None)
        if bus is None or not self.controller.running:
            return False
        try:
            if action == "left_volume":
                self.controller.set_bus_channel_volume(bus.id, "left", bus.left_volume)
            elif action == "right_volume":
                self.controller.set_bus_channel_volume(bus.id, "right", bus.right_volume)
            elif action == "mic_volume":
                self.controller.set_bus_mic_volume(
                    bus.id,
                    bus.mic_volume,
                    bus.mic_left_enabled,
                    bus.mic_right_enabled,
                )
        except PulseAudioError as error:
            self._set_status(f"调整音量失败：{error}", "error")
        return False

    def _available_sinks(self, sinks: list[Sink]) -> list[Sink]:
        result = [
            sink
            for sink in sinks
            if sink.driver != "module-null-sink.c"
            and sink.driver != "module-remap-sink.c"
            and "front-left" in sink.channel_map
            and "front-right" in sink.channel_map
        ]
        return sorted(result, key=lambda sink: sink.description.lower())

    def _available_sources(self, sources: list[Source]) -> list[Source]:
        result = [
            source
            for source in sources
            if not source.name.startswith("am_route_")
        ]

        def sort_key(source: Source):
            if source.name.startswith(VI_PREFIX):
                suffix = source.name.removeprefix(VI_PREFIX).removesuffix(".monitor")
                return (0, int(suffix) if suffix.isdigit() else 99, source.description)
            if not source.monitor_of_sink:
                return (1, 0, source.description)
            return (2, 0, source.description)

        return sorted(result, key=sort_key)

    def _virtual_source_name(self, index: int) -> str:
        name = f"{VI_PREFIX}{index}.monitor"
        return name if any(source.name == name for source in self.sources) else ""

    def _refresh_applications(self, force: bool = False) -> None:
        if self._apps_loading:
            return
        try:
            raw_sinks = self.pulse.sinks()
            streams = self.pulse.sink_inputs()
            owned = self.controller.owned_module_indices()
        except PulseAudioError as error:
            self._set_status(f"读取应用音频失败：{error}", "error")
            return

        streams = [stream for stream in streams if stream.owner_module not in owned]
        virtual_sinks = sorted(
            (sink for sink in raw_sinks if sink.name.startswith(VI_PREFIX)),
            key=lambda sink: sink.name,
        )
        sink_by_index = {sink.index: sink for sink in raw_sinks}
        signature = tuple(
            (
                stream.index,
                stream.label,
                stream.media_name,
                sink_by_index.get(stream.sink_index, Sink(-1, "", "", "", (), "")).name,
            )
            for stream in streams
        )
        if not force and signature == self._app_signature:
            return
        self._app_signature = signature
        self._apps_loading = True
        try:
            for child in self.apps_box.get_children():
                self.apps_box.remove(child)
            if not streams:
                empty = Gtk.Label(
                    label="当前没有正在播放的应用音频。播放声音后点击“刷新应用”。"
                )
                empty.get_style_context().add_class("hint")
                empty.set_xalign(0)
                self.apps_box.pack_start(empty, False, False, 0)
                self.apps_box.show_all()
                return

            primary_sink = next(
                (
                    sink
                    for sink in raw_sinks
                    if self.config.buses and sink.name == self.config.buses[0].output_sink
                ),
                None,
            )
            for stream in sorted(streams, key=lambda item: item.label.lower()):
                current = sink_by_index.get(stream.sink_index)
                if current is not None and current.name.startswith(VI_PREFIX):
                    target = current.name
                else:
                    target = self.config.app_routes.get(stream.identity, "")
                row = ApplicationRow(
                    stream,
                    virtual_sinks,
                    primary_sink,
                    target,
                    self._on_app_target_changed,
                    self._on_app_volume_changed,
                    self._on_app_mute_changed,
                )
                self.apps_box.pack_start(row.card, False, False, 0)
            self.apps_box.show_all()
        finally:
            self._apps_loading = False

    def _on_app_target_changed(self, stream: SinkInput, target: str) -> None:
        if self._apps_loading:
            return
        try:
            if target == DIRECT_OUTPUT:
                primary = self.config.buses[0].output_sink
                self.controller.move_application(stream, primary)
                self.config.app_routes.pop(stream.identity, None)
                self._set_status(f"已将 {stream.label} 直接送到总线 1。", "ok")
            elif target:
                self.controller.move_application(stream, target)
                self.config.app_routes[stream.identity] = target
                self._set_status(f"已分流 {stream.label}。", "ok")
            else:
                self.config.app_routes.pop(stream.identity, None)
        except PulseAudioError as error:
            self._set_status(f"移动应用失败：{error}", "error")
        self._save_config()
        GLib.timeout_add(120, lambda: self._refresh_applications(force=True) or False)

    def _on_app_volume_changed(self, stream: SinkInput, volume: int) -> None:
        if self._apps_loading:
            return
        try:
            channels = max(1, len(stream.channel_map))
            self.pulse.set_sink_input_volume(stream.index, volume, channels)
        except PulseAudioError as error:
            self._set_status(f"调整应用音量失败：{error}", "error")

    def _on_app_mute_changed(self, stream: SinkInput, muted: bool) -> None:
        if self._apps_loading:
            return
        try:
            self.pulse.set_sink_input_mute(stream.index, muted)
        except PulseAudioError as error:
            self._set_status(f"设置应用静音失败：{error}", "error")

    def _update_warnings(self) -> None:
        try:
            pulsemeeter_running = self.controller.detect_pulsemeeter()
        except PulseAudioError:
            pulsemeeter_running = False
        self.compat_warning.set_visible(pulsemeeter_running)

    def _on_mic_source_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self._loading:
            return
        source = combo.get_active_id()
        if source is None:
            return
        self.config.mic_source = source
        self._save_config()
        self._schedule_restart()

    def _schedule_restart(self) -> None:
        if not self.controller.running or self._restart_pending:
            return
        self._restart_pending = True
        GLib.timeout_add(180, self._restart_live)

    def _restart_live(self) -> bool:
        self._restart_pending = False
        if self.controller.running:
            self._apply_routing(silent=True)
        return False

    def _start_routing(self, _button: Gtk.Button) -> None:
        self._apply_routing(silent=False)

    def _apply_routing(self, silent: bool) -> None:
        if not self.config.buses:
            self._set_status("请至少创建一条输出总线。", "error")
            return
        specs = [
            BusRouteSpec(
                bus_id=bus.id,
                name=bus.name,
                output_sink=bus.output_sink,
                left_source=bus.left_source,
                right_source=bus.right_source,
                left_volume=bus.left_volume,
                right_volume=bus.right_volume,
                left_muted=bus.left_muted,
                right_muted=bus.right_muted,
                mic_enabled=bus.mic_enabled,
                mic_left_enabled=bus.mic_left_enabled,
                mic_right_enabled=bus.mic_right_enabled,
                mic_volume=bus.mic_volume,
            )
            for bus in self.config.buses
        ]
        self._set_status("正在建立独立输出总线…", "warn")
        try:
            self.controller.apply_buses(
                specs,
                mic_source=self.config.mic_source,
                latency_ms=self.config.latency_ms,
            )
        except PulseAudioError as error:
            self._set_status(f"启动音频矩阵失败：{error}", "error")
            self.stop_button.set_sensitive(False)
            if not silent:
                self._show_error("无法启动音频矩阵", str(error))
            return

        self.stop_button.set_sensitive(True)
        self.route_button.set_label("重新连接")
        self._update_warnings()
        self._set_status(
            f"正在运行 {len(self.config.buses)} 条独立输出总线，"
            f"共 {len(self.controller.active.routes)} 条左右/麦克风路由。",
            "ok",
        )

    def _stop_routing(self, _button: Gtk.Button | None = None) -> None:
        try:
            self.controller.stop_routes()
            self._set_status("所有输出总线已停止，应用分流配置仍然保留。", "ok")
        except PulseAudioError as error:
            self._set_status(f"停止输出时出错：{error}", "error")
        self.stop_button.set_sensitive(False)
        self.route_button.set_label("启动所有总线")

    def _auto_start(self) -> bool:
        if self.config.buses:
            self._apply_routing(silent=True)
        return False

    def _periodic_tick(self) -> bool:
        if not self._engine_ready:
            return True
        try:
            moved = self.controller.sync_application_routes(self.config.app_routes)
            if moved:
                self._set_status(f"已自动恢复 {moved} 个应用的音频分流。", "ok")
            self._refresh_applications()
            expected = 3 + 2 * len(
                [route for route in self.controller.active.routes.values() if route.module_id]
            )
            if len(self.controller.owned_modules()) < expected:
                if self.controller.running:
                    self.controller.stop_routes()
                    self.stop_button.set_sensitive(False)
                    self.route_button.set_label("重新连接")
                    self._set_status("输出路由已断开，请重新连接。", "error")
                self._engine_ready = False
                self.refresh_all()
            self._update_warnings()
        except PulseAudioError as error:
            self._set_status(f"音频服务异常：{error}", "error")
        return True

    def _on_auto_start_changed(self, button: Gtk.CheckButton) -> None:
        if self._loading:
            return
        self.config.auto_start = button.get_active()
        self._save_config()

    def _save_config(self) -> None:
        if self._save_pending:
            return
        self._save_pending = True
        GLib.timeout_add(250, self._write_config)

    def _write_config(self) -> bool:
        self._save_pending = False
        try:
            self.config_store.save(self.config)
        except OSError as error:
            self._set_status(f"保存配置失败：{error}", "error")
        return False

    def _show_error(self, title: str, message: str) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text=title,
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def _on_destroy(self, _window: Gtk.Widget) -> None:
        if self._health_timer:
            GLib.source_remove(self._health_timer)
        for timer in self._volume_timers.values():
            GLib.source_remove(timer)
        try:
            self.controller.shutdown()
        except PulseAudioError:
            pass
        try:
            self.config_store.save(self.config)
        except OSError:
            pass


def source_label(source: Source) -> str:
    channel_name = source.name.removesuffix(".monitor")
    if channel_name.startswith(VI_PREFIX):
        suffix = channel_name.removeprefix(VI_PREFIX)
        return f"音频矩阵 · 输入 {suffix}"
    if not source.monitor_of_sink:
        return f"麦克风 / 输入 · {source.description}"
    return f"系统通道 · {source.description}"


class AudioMatrixApplication(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.window: MainWindow | None = None

    def do_activate(self) -> None:
        if self.window is None:
            self.window = MainWindow(self)
        self.window.show_all()
        self.window.present()


def main() -> int:
    app = AudioMatrixApplication()
    return app.run(sys.argv)
