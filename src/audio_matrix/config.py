from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class OutputBusConfig:
    id: str = "bus_1"
    name: str = "总线 1"
    output_sink: str = ""
    left_source: str = ""
    right_source: str = ""
    left_volume: int = 100
    right_volume: int = 100
    left_muted: bool = False
    right_muted: bool = False
    mic_enabled: bool = False
    mic_left_enabled: bool = True
    mic_right_enabled: bool = True
    mic_volume: int = 100


@dataclass
class AppConfig:
    buses: list[OutputBusConfig] = field(
        default_factory=lambda: [OutputBusConfig()]
    )
    mic_source: str = ""
    latency_ms: int = 120
    auto_start: bool = False
    app_routes: dict[str, str] = field(default_factory=dict)


def config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "audio-matrix" / "config.json"


def _as_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def _bus_from_dict(raw: dict[str, Any], index: int) -> OutputBusConfig:
    bus_number = index + 1
    bus_id = str(raw.get("id") or f"bus_{bus_number}")
    name = str(raw.get("name") or f"总线 {bus_number}")
    return OutputBusConfig(
        id=bus_id,
        name=name,
        output_sink=str(raw.get("output_sink") or ""),
        left_source=str(raw.get("left_source") or ""),
        right_source=str(raw.get("right_source") or ""),
        left_volume=_as_int(raw.get("left_volume"), 100, 0, 100),
        right_volume=_as_int(raw.get("right_volume"), 100, 0, 100),
        left_muted=bool(raw.get("left_muted", False)),
        right_muted=bool(raw.get("right_muted", False)),
        mic_enabled=bool(raw.get("mic_enabled", False)),
        mic_left_enabled=bool(raw.get("mic_left_enabled", True)),
        mic_right_enabled=bool(raw.get("mic_right_enabled", True)),
        mic_volume=_as_int(raw.get("mic_volume"), 100, 0, 100),
    )


class ConfigStore:
    def __init__(self, path: Path | None = None):
        self.path = path or config_path()

    def load(self) -> AppConfig:
        try:
            raw: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError, TypeError):
            return AppConfig()

        buses_raw = raw.get("buses")
        buses: list[OutputBusConfig] = []
        if isinstance(buses_raw, list):
            for index, item in enumerate(buses_raw):
                if isinstance(item, dict):
                    buses.append(_bus_from_dict(item, index))
        elif raw.get("output_sink"):
            mic_enabled = bool(raw.get("mic_monitor_enabled", False))
            mic_left = bool(raw.get("mic_left_enabled", True))
            mic_right = bool(raw.get("mic_right_enabled", True))
            mic_volume = _as_int(raw.get("mic_volume"), 100, 0, 100)
            primary = OutputBusConfig(
                id="bus_1",
                name="总线 1",
                output_sink=str(raw.get("output_sink") or ""),
                left_source=str(raw.get("left_source") or ""),
                right_source=str(raw.get("right_source") or ""),
                left_volume=_as_int(raw.get("left_volume"), 100, 0, 100),
                right_volume=_as_int(raw.get("right_volume"), 100, 0, 100),
                left_muted=bool(raw.get("left_muted", False)),
                right_muted=bool(raw.get("right_muted", False)),
                mic_enabled=mic_enabled,
                mic_left_enabled=mic_left,
                mic_right_enabled=mic_right,
                mic_volume=mic_volume,
            )
            buses.append(primary)
            for index, sink_name in enumerate(
                raw.get("extra_output_sinks", []), start=2
            ):
                if not isinstance(sink_name, str):
                    continue
                buses.append(
                    OutputBusConfig(
                        id=f"bus_{index}",
                        name=f"总线 {index}",
                        output_sink=sink_name,
                        left_source=primary.left_source,
                        right_source=primary.right_source,
                        left_volume=primary.left_volume,
                        right_volume=primary.right_volume,
                        left_muted=primary.left_muted,
                        right_muted=primary.right_muted,
                        mic_enabled=primary.mic_enabled,
                        mic_left_enabled=primary.mic_left_enabled,
                        mic_right_enabled=primary.mic_right_enabled,
                        mic_volume=primary.mic_volume,
                    )
                )

        if not buses:
            buses = [OutputBusConfig()]

        seen_ids: set[str] = set()
        for index, bus in enumerate(buses):
            if bus.id in seen_ids:
                bus.id = f"bus_{index + 1}"
            seen_ids.add(bus.id)

        routes = raw.get("app_routes")
        if not isinstance(routes, dict):
            routes = {}
        routes = {
            str(key): str(target)
            for key, target in routes.items()
            if isinstance(key, str) and isinstance(target, str)
        }

        return AppConfig(
            buses=buses,
            mic_source=str(raw.get("mic_source") or ""),
            latency_ms=_as_int(raw.get("latency_ms"), 120, 20, 2000),
            auto_start=bool(raw.get("auto_start", False)),
            app_routes=routes,
        )

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(asdict(config), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(self.path)
