from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from audio_matrix.config import AppConfig, ConfigStore, OutputBusConfig


class ConfigStoreTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            expected = AppConfig(
                buses=[
                    OutputBusConfig(
                        id="bus_1",
                        name="耳机",
                        output_sink="output-1",
                        left_source="left",
                        right_source="right",
                        left_volume=67,
                        right_volume=43,
                        left_muted=True,
                        right_muted=False,
                        mic_enabled=True,
                        mic_left_enabled=True,
                        mic_right_enabled=False,
                        mic_volume=72,
                    ),
                    OutputBusConfig(
                        id="bus_2",
                        name="音箱",
                        output_sink="output-2",
                        left_source="right",
                        right_source="left",
                    ),
                ],
                latency_ms=160,
                auto_start=True,
                mic_source="microphone",
                app_routes={"firefox|Music": "am_input_2"},
            )
            store.save(expected)
            self.assertEqual(store.load(), expected)

    def test_invalid_values_are_clamped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                '{"buses": [{"left_volume": 900, "right_volume": -4}], "latency_ms": 1}',
                encoding="utf-8",
            )
            config = ConfigStore(path).load()
            self.assertEqual(config.buses[0].left_volume, 100)
            self.assertEqual(config.buses[0].right_volume, 0)
            self.assertEqual(config.latency_ms, 20)

    def test_legacy_outputs_become_independent_buses(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                """
                {
                  "output_sink": "hdmi",
                  "extra_output_sinks": ["usb"],
                  "left_source": "am_input_1.monitor",
                  "right_source": "am_input_2.monitor",
                  "left_volume": 80,
                  "right_volume": 70,
                  "mic_source": "mic",
                  "mic_monitor_enabled": true
                }
                """,
                encoding="utf-8",
            )
            config = ConfigStore(path).load()
            self.assertEqual([bus.output_sink for bus in config.buses], ["hdmi", "usb"])
            self.assertEqual(config.buses[1].left_volume, 80)
            self.assertTrue(config.buses[1].mic_enabled)


if __name__ == "__main__":
    unittest.main()
