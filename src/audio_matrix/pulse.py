from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Iterable


VI_PREFIX = "am_input_"
VI_DESCRIPTIONS = {
    1: "AM_Virtual_Input_1",
    2: "AM_Virtual_Input_2",
    3: "AM_Virtual_Input_3",
}
VI_MARKER = f"sink_name={VI_PREFIX}"
ROUTE_MARKER = "device.description=AM_Route_"


class PulseAudioError(RuntimeError):
    pass


@dataclass(frozen=True)
class Sink:
    index: int
    name: str
    description: str
    driver: str
    channel_map: tuple[str, ...]
    monitor_source: str


@dataclass(frozen=True)
class Source:
    index: int
    name: str
    description: str
    state: str
    monitor_of_sink: str


@dataclass(frozen=True)
class Module:
    index: int
    name: str
    arguments: str


@dataclass(frozen=True)
class SourceOutput:
    index: int
    owner_module: int
    source: str


@dataclass(frozen=True)
class SinkInput:
    index: int
    owner_module: int
    sink_index: int
    app_name: str
    binary: str
    media_name: str
    channel_map: tuple[str, ...]
    muted: bool
    volume: int

    @property
    def label(self) -> str:
        return self.app_name or self.binary or self.media_name or "未知应用"

    @property
    def identity(self) -> str:
        parts = (self.binary or self.app_name, self.media_name)
        return "|".join(part.strip() for part in parts if part.strip())


@dataclass
class RouteState:
    module_id: int | None = None
    input_module_id: int | None = None
    source_output_index: int | None = None
    sink_input_index: int | None = None


@dataclass(frozen=True)
class BusRouteSpec:
    bus_id: str
    name: str
    output_sink: str
    left_source: str
    right_source: str
    left_volume: int
    right_volume: int
    left_muted: bool
    right_muted: bool
    mic_enabled: bool
    mic_left_enabled: bool
    mic_right_enabled: bool
    mic_volume: int


@dataclass
class ActiveRoutes:
    output_sinks: list[str] = field(default_factory=list)
    downmix_modules: dict[str, int] = field(default_factory=dict)
    routes: dict[str, RouteState] = field(default_factory=dict)

    @property
    def running(self) -> bool:
        return bool(
            self.output_sinks
            and any(route.module_id is not None for route in self.routes.values())
        )


def _clean_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _field(block: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}:\s*(.*?)\s*$", block, re.MULTILINE)
    return _clean_value(match.group(1)) if match else ""


def _property(block: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*(\".*?\"|'.*?'|\S.*?)\s*$", block, re.MULTILINE)
    return _clean_value(match.group(1)) if match else ""


def _split_blocks(text: str) -> Iterable[str]:
    yield from (block.strip() for block in re.split(r"\n\s*\n", text) if block.strip())


def _volume_percent(block: str) -> int:
    values = [int(value) for value in re.findall(r"(\d+)%", _field(block, "Volume"))]
    if not values:
        return 100
    return max(0, min(100, max(values)))


def parse_sinks(text: str) -> list[Sink]:
    sinks: list[Sink] = []
    for block in _split_blocks(text):
        match = re.match(r"Sink\s+#(\d+)", block)
        if not match:
            continue
        channel_map = tuple(
            channel.strip()
            for channel in _field(block, "Channel Map").split(",")
            if channel.strip()
        )
        sinks.append(
            Sink(
                index=int(match.group(1)),
                name=_field(block, "Name"),
                description=_field(block, "Description"),
                driver=_field(block, "Driver"),
                channel_map=channel_map,
                monitor_source=_field(block, "Monitor Source"),
            )
        )
    return sinks


def parse_sources(text: str) -> list[Source]:
    sources: list[Source] = []
    for block in _split_blocks(text):
        match = re.match(r"Source\s+#(\d+)", block)
        if not match:
            continue
        monitor_of_sink = _field(block, "Monitor of Sink")
        if monitor_of_sink.lower() == "n/a":
            monitor_of_sink = ""
        sources.append(
            Source(
                index=int(match.group(1)),
                name=_field(block, "Name"),
                description=_field(block, "Description"),
                state=_field(block, "State"),
                monitor_of_sink=monitor_of_sink,
            )
        )
    return sources


def parse_source_outputs(text: str) -> list[SourceOutput]:
    outputs: list[SourceOutput] = []
    for block in _split_blocks(text):
        match = re.match(r"Source Output\s+#(\d+)", block)
        if not match:
            continue
        owner_module = _field(block, "Owner Module")
        try:
            module_index = int(owner_module)
        except ValueError:
            continue
        outputs.append(
            SourceOutput(
                index=int(match.group(1)),
                owner_module=module_index,
                source=_field(block, "Source"),
            )
        )
    return outputs


def parse_sink_inputs(text: str) -> list[SinkInput]:
    inputs: list[SinkInput] = []
    for block in _split_blocks(text):
        match = re.match(r"Sink Input\s+#(\d+)", block)
        if not match:
            continue
        try:
            owner_module = int(_field(block, "Owner Module"))
            sink_index = int(_field(block, "Sink"))
        except ValueError:
            continue
        channel_map = tuple(
            channel.strip()
            for channel in _field(block, "Channel Map").split(",")
            if channel.strip()
        )
        inputs.append(
            SinkInput(
                index=int(match.group(1)),
                owner_module=owner_module,
                sink_index=sink_index,
                app_name=_property(block, "application.name"),
                binary=_property(block, "application.process.binary"),
                media_name=_property(block, "media.name"),
                channel_map=channel_map,
                muted=_field(block, "Mute").lower() == "yes",
                volume=_volume_percent(block),
            )
        )
    return inputs


class PulseAudio:
    def __init__(self, executable: str = "pactl"):
        self.executable = executable

    def _run(self, *args: str, check: bool = True) -> str:
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        env["LANG"] = "C"
        try:
            process = subprocess.run(
                [self.executable, *args],
                capture_output=True,
                text=True,
                env=env,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise PulseAudioError(f"无法调用 PulseAudio：{error}") from error

        if check and process.returncode != 0:
            message = process.stderr.strip() or process.stdout.strip() or "未知错误"
            raise PulseAudioError(message)
        return process.stdout

    def available(self) -> bool:
        try:
            info = self._run("info")
        except PulseAudioError:
            return False
        return "Server Name:" in info

    def sinks(self) -> list[Sink]:
        return parse_sinks(self._run("list", "sinks"))

    def sources(self) -> list[Source]:
        return parse_sources(self._run("list", "sources"))

    def source_outputs(self) -> list[SourceOutput]:
        return parse_source_outputs(self._run("list", "source-outputs"))

    def sink_inputs(self) -> list[SinkInput]:
        return parse_sink_inputs(self._run("list", "sink-inputs"))

    def modules(self) -> list[Module]:
        modules: list[Module] = []
        for line in self._run("list", "short", "modules").splitlines():
            parts = line.split("\t", 2)
            if len(parts) < 2:
                continue
            try:
                index = int(parts[0])
            except ValueError:
                continue
            modules.append(
                Module(
                    index=index,
                    name=parts[1],
                    arguments=parts[2] if len(parts) > 2 else "",
                )
            )
        return modules

    def load_module(self, name: str, *arguments: str) -> int:
        output = self._run("load-module", name, *arguments).strip()
        try:
            return int(output)
        except ValueError as error:
            raise PulseAudioError(f"PulseAudio 返回了无效模块编号：{output}") from error

    def unload_module(self, index: int) -> None:
        self._run("unload-module", str(index))

    def move_sink_input(self, index: int, sink_name: str) -> None:
        self._run("move-sink-input", str(index), sink_name)

    def set_sink_input_volume(
        self, index: int, volume: int, channel_count: int = 2
    ) -> None:
        volume = max(0, min(100, int(volume)))
        channel_count = max(1, min(8, channel_count))
        self._run(
            "set-sink-input-volume",
            str(index),
            *[f"{volume}%"] * channel_count,
        )

    def set_sink_input_mute(self, index: int, muted: bool) -> None:
        self._run("set-sink-input-mute", str(index), "1" if muted else "0")

    def set_route_channel_volume(
        self, index: int, left_volume: int, right_volume: int
    ) -> None:
        left_volume = max(0, min(100, int(left_volume)))
        right_volume = max(0, min(100, int(right_volume)))
        self._run(
            "set-sink-input-volume",
            str(index),
            f"{left_volume}%",
            f"{right_volume}%",
        )

    def set_source_output_mute(self, index: int, muted: bool) -> None:
        self._run("set-source-output-mute", str(index), "1" if muted else "0")


class AudioMatrixController:
    """Creates and owns Audio Matrix PulseAudio modules."""

    def __init__(self, pulse: PulseAudio | None = None):
        self.pulse = pulse or PulseAudio()
        self.active = ActiveRoutes()
        self.virtual_input_modules: dict[str, int] = {}

    @property
    def running(self) -> bool:
        return self.active.running

    def owned_modules(self) -> list[Module]:
        return [
            module
            for module in self.pulse.modules()
            if VI_MARKER in module.arguments or ROUTE_MARKER in module.arguments
        ]

    def owned_module_indices(self) -> set[int]:
        return {module.index for module in self.owned_modules()}

    def detect_pulsemeeter(self) -> bool:
        arguments = "\n".join(module.arguments for module in self.pulse.modules())
        return "sink_name=Virtual_Input_1" in arguments

    @staticmethod
    def pulsemeeter_process_running() -> bool:
        try:
            process = subprocess.run(
                ["pgrep", "-f", r"(^|/)pulsemeeter( |$)"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return process.returncode == 0

    def cleanup_stale_pulsemeeter(self) -> int:
        modules = self.pulse.modules()
        pulsemeeter_modules = [
            module
            for module in modules
            if module.name == "module-null-sink"
            and (
                "sink_name=Virtual_Input_" in module.arguments
                or "sink_name=Virtual_Output_B" in module.arguments
            )
        ]
        if not pulsemeeter_modules or self.pulsemeeter_process_running():
            return 0

        removed = 0
        orphan_loopbacks = [
            module
            for module in modules
            if module.name == "module-loopback"
            and ROUTE_MARKER not in module.arguments
        ]
        related = [
            module
            for module in modules
            if module.name == "module-remap-source"
            and "source_name=Virtual_Output_B" in module.arguments
        ]
        for module in [*orphan_loopbacks, *related, *pulsemeeter_modules]:
            try:
                self.pulse.unload_module(module.index)
                removed += 1
            except PulseAudioError:
                pass
        return removed

    def virtual_input_sinks(self) -> list[Sink]:
        return sorted(
            (
                sink
                for sink in self.pulse.sinks()
                if sink.name.startswith(VI_PREFIX)
            ),
            key=lambda sink: sink.name,
        )

    def ensure_engine(self) -> None:
        existing = [
            module
            for module in self.pulse.modules()
            if module.name == "module-null-sink"
            and VI_MARKER in module.arguments
        ]
        expected_sinks = {
            f"{VI_PREFIX}{index}": VI_DESCRIPTIONS[index] for index in range(1, 4)
        }
        existing_names = {
            match.group(1)
            for module in existing
            if (match := re.search(r"sink_name=(\S+)", module.arguments))
        }
        if existing_names == set(expected_sinks) and not self.active.running:
            self._wait_for_virtual_sources()
            return

        for module in existing:
            try:
                self.pulse.unload_module(module.index)
            except PulseAudioError:
                pass
        self.virtual_input_modules.clear()

        for index in range(1, 4):
            sink_name = f"{VI_PREFIX}{index}"
            description = VI_DESCRIPTIONS[index]
            module_id = self.pulse.load_module(
                "module-null-sink",
                f"sink_name={sink_name}",
                f"sink_properties=device.description={description}",
                "channels=2",
                "channel_map=front-left,front-right",
                "rate=48000",
            )
            self.virtual_input_modules[sink_name] = module_id
        self._wait_for_virtual_sources()

    def _wait_for_virtual_sources(self) -> None:
        expected = {f"{VI_PREFIX}{index}.monitor" for index in range(1, 4)}
        for _ in range(20):
            available = {source.name for source in self.pulse.sources()}
            if expected.issubset(available):
                return
            time.sleep(0.05)

    def cleanup_routes(self) -> None:
        route_modules = [
            module
            for module in self.pulse.modules()
            if ROUTE_MARKER in module.arguments
        ]
        loopbacks = [module for module in route_modules if module.name == "module-loopback"]
        remap_sources = [
            module for module in route_modules if module.name == "module-remap-source"
        ]
        for module in [*loopbacks, *remap_sources]:
            try:
                self.pulse.unload_module(module.index)
            except PulseAudioError:
                pass
        self.active = ActiveRoutes()

    def shutdown(self) -> None:
        self.cleanup_routes()
        modules = [
            module
            for module in self.pulse.modules()
            if VI_MARKER in module.arguments
        ]
        for module in modules:
            try:
                self.pulse.unload_module(module.index)
            except PulseAudioError:
                pass
        self.virtual_input_modules.clear()

    def _create_route(
        self,
        route_id: str,
        source: str,
        output_sink: str,
        left_volume: int,
        right_volume: int,
        latency_ms: int,
        muted: bool,
    ) -> RouteState:
        safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", route_id)
        downmix_source = f"am_route_{safe_id}_downmix"
        downmix_module = self.pulse.load_module(
            "module-remap-source",
            f"source_name={downmix_source}",
            f"master={source}",
            f"source_properties={ROUTE_MARKER}{safe_id}_Downmix",
            "channels=1",
            "channel_map=mono",
            "remix=yes",
        )
        self.active.downmix_modules[route_id] = downmix_module

        output_module = self.pulse.load_module(
            "module-loopback",
            f"source={downmix_source}",
            f"sink={output_sink}",
            "channels=2",
            "channel_map=front-left,front-right",
            "remix=yes",
            f"latency_msec={latency_ms}",
            "source_dont_move=true",
            "sink_dont_move=true",
            f"source_output_properties={ROUTE_MARKER}{safe_id}_Output",
            f"sink_input_properties={ROUTE_MARKER}{safe_id}_Output",
        )

        route = RouteState(module_id=output_module, input_module_id=downmix_module)
        for _ in range(20):
            if route.source_output_index is None:
                for source_output in self.pulse.source_outputs():
                    if source_output.owner_module == output_module:
                        route.source_output_index = source_output.index
                        break
            if route.sink_input_index is None:
                for sink_input in self.pulse.sink_inputs():
                    if sink_input.owner_module == output_module:
                        route.sink_input_index = sink_input.index
                        break
            if route.source_output_index is not None and route.sink_input_index is not None:
                break
            time.sleep(0.05)

        if route.sink_input_index is not None:
            self.pulse.set_route_channel_volume(
                route.sink_input_index, left_volume, right_volume
            )
        if route.source_output_index is not None:
            self.pulse.set_source_output_mute(route.source_output_index, muted)
        return route

    def apply_buses(
        self,
        buses: list[BusRouteSpec],
        mic_source: str,
        latency_ms: int,
    ) -> None:
        self.cleanup_routes()
        sinks = {sink.name: sink for sink in self.pulse.sinks()}
        if not buses:
            raise PulseAudioError("至少需要配置一条输出总线。")
        for bus in buses:
            sink = sinks.get(bus.output_sink)
            if sink is None:
                raise PulseAudioError(
                    f"{bus.name} 的输出设备已经不可用：{bus.output_sink}"
                )
            if (
                "front-left" not in sink.channel_map
                or "front-right" not in sink.channel_map
            ):
                raise PulseAudioError(f"{bus.name} 的输出不是双声道设备。")

        available_sources = {source.name for source in self.pulse.sources()}
        requested: list[tuple[str, str]] = []
        for bus in buses:
            requested.extend(
                [
                    (f"{bus.name} · 左声道", bus.left_source),
                    (f"{bus.name} · 右声道", bus.right_source),
                    (
                        f"{bus.name} · 麦克风",
                        mic_source if bus.mic_enabled else "",
                    ),
                ]
            )
        for label, source in requested:
            if source and source not in available_sources:
                raise PulseAudioError(f"{label}来源已经不可用，请刷新设备后重选。")

        if not any(
            bus.left_source
            or bus.right_source
            or (
                bus.mic_enabled
                and mic_source
                and (bus.mic_left_enabled or bus.mic_right_enabled)
            )
            for bus in buses
        ):
            raise PulseAudioError("至少需要选择一个左声道、右声道或麦克风来源。")

        self.active.output_sinks = list(
            dict.fromkeys(bus.output_sink for bus in buses)
        )
        try:
            for bus in buses:
                route_prefix = bus.bus_id
                if bus.left_source:
                    self.active.routes[f"{route_prefix}:left"] = self._create_route(
                        f"{route_prefix}:left",
                        bus.left_source,
                        bus.output_sink,
                        bus.left_volume,
                        0,
                        latency_ms,
                        bus.left_muted,
                    )
                if bus.right_source:
                    self.active.routes[f"{route_prefix}:right"] = self._create_route(
                        f"{route_prefix}:right",
                        bus.right_source,
                        bus.output_sink,
                        0,
                        bus.right_volume,
                        latency_ms,
                        bus.right_muted,
                    )
                if bus.mic_enabled and mic_source:
                    mic_left_gain = bus.mic_volume if bus.mic_left_enabled else 0
                    mic_right_gain = bus.mic_volume if bus.mic_right_enabled else 0
                    if mic_source == bus.left_source:
                        mic_left_gain = 0
                    if mic_source == bus.right_source:
                        mic_right_gain = 0
                    if mic_left_gain or mic_right_gain:
                        self.active.routes[f"{route_prefix}:mic"] = self._create_route(
                            f"{route_prefix}:mic",
                            mic_source,
                            bus.output_sink,
                            mic_left_gain,
                            mic_right_gain,
                            latency_ms,
                            False,
                        )
        except PulseAudioError:
            self.cleanup_routes()
            raise

    def stop_routes(self) -> None:
        self.cleanup_routes()

    def set_bus_channel_volume(self, bus_id: str, channel: str, volume: int) -> None:
        route = self.active.routes.get(f"{bus_id}:{channel}")
        if route and route.sink_input_index is not None:
            if channel == "left":
                self.pulse.set_route_channel_volume(route.sink_input_index, volume, 0)
            else:
                self.pulse.set_route_channel_volume(route.sink_input_index, 0, volume)

    def set_bus_channel_mute(self, bus_id: str, channel: str, muted: bool) -> None:
        route = self.active.routes.get(f"{bus_id}:{channel}")
        if route and route.source_output_index is not None:
            self.pulse.set_source_output_mute(route.source_output_index, muted)

    def set_bus_mic_volume(
        self,
        bus_id: str,
        volume: int,
        left_enabled: bool,
        right_enabled: bool,
    ) -> None:
        route = self.active.routes.get(f"{bus_id}:mic")
        if route and route.sink_input_index is not None:
            self.pulse.set_route_channel_volume(
                route.sink_input_index,
                volume if left_enabled else 0,
                volume if right_enabled else 0,
            )

    def move_application(self, stream: SinkInput, target_sink: str) -> None:
        sinks = {sink.name: sink for sink in self.pulse.sinks()}
        target = sinks.get(target_sink)
        if target is None:
            raise PulseAudioError("目标虚拟输入已经不可用。")
        if stream.sink_index != target.index:
            self.pulse.move_sink_input(stream.index, target_sink)

    def sync_application_routes(self, rules: dict[str, str]) -> int:
        if not rules:
            return 0
        sinks = {sink.name: sink for sink in self.pulse.sinks()}
        owned_modules = self.owned_module_indices()
        moved = 0
        for stream in self.pulse.sink_inputs():
            if stream.owner_module in owned_modules:
                continue
            target_name = rules.get(stream.identity)
            target = sinks.get(target_name or "")
            if target is None or stream.sink_index == target.index:
                continue
            try:
                self.pulse.move_sink_input(stream.index, target.name)
                moved += 1
            except PulseAudioError:
                continue
        return moved
