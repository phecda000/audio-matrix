from __future__ import annotations

import unittest

from audio_matrix.pulse import (
    parse_sink_inputs,
    parse_sinks,
    parse_source_outputs,
    parse_sources,
)


SINKS = """Sink #2
\tState: RUNNING
\tName: alsa_output.test.analog-stereo
\tDescription: Test Analog Stereo
\tDriver: module-alsa-card.c
\tChannel Map: front-left,front-right
\tMonitor Source: alsa_output.test.analog-stereo.monitor

Sink #5
\tState: IDLE
\tName: Virtual_Input_1
\tDescription: Virtual_Input_1
\tDriver: module-null-sink.c
\tChannel Map: front-left,front-right
\tMonitor Source: Virtual_Input_1.monitor
"""

SOURCES = """Source #3
\tState: RUNNING
\tName: alsa_input.test.analog-stereo
\tDescription: Test Microphone
\tMonitor of Sink: n/a

Source #9
\tState: IDLE
\tName: Virtual_Input_1.monitor
\tDescription: Monitor of Virtual_Input_1
\tMonitor of Sink: Virtual_Input_1
"""

SOURCE_OUTPUTS = """Source Output #22
\tOwner Module: 51
\tSource: Virtual_Input_1.monitor

Source Output #23
\tOwner Module: 52
\tSource: alsa_input.test.analog-stereo
"""

SINK_INPUTS = """Sink Input #30
\tOwner Module: 51
\tSink: 2
\tMute: no
\tVolume: front-left: 65536 / 100% / 0.00 dB,   front-right: 32768 / 50% / -18.06 dB
\tChannel Map: front-left,front-right
\tProperties:
\t\tapplication.name = "Firefox"
\t\tapplication.process.binary = "firefox"
\t\tmedia.name = "Music tab"

Sink Input #31
\tOwner Module: 52
\tSink: 2
\tMute: yes
\tVolume: mono: 16384 / 25% / -24.08 dB
\tChannel Map: mono
\tProperties:
\t\tapplication.name = "VLC"
\t\tapplication.process.binary = "vlc"
\t\tmedia.name = "Video"
"""


class PulseParserTests(unittest.TestCase):
    def test_parse_sinks(self):
        sinks = parse_sinks(SINKS)
        self.assertEqual([sink.index for sink in sinks], [2, 5])
        self.assertEqual(sinks[0].description, "Test Analog Stereo")
        self.assertEqual(sinks[0].channel_map, ("front-left", "front-right"))
        self.assertEqual(sinks[1].monitor_source, "Virtual_Input_1.monitor")

    def test_parse_sources(self):
        sources = parse_sources(SOURCES)
        self.assertEqual(sources[0].description, "Test Microphone")
        self.assertEqual(sources[0].monitor_of_sink, "")
        self.assertEqual(sources[1].monitor_of_sink, "Virtual_Input_1")

    def test_parse_source_outputs(self):
        outputs = parse_source_outputs(SOURCE_OUTPUTS)
        self.assertEqual(
            [(output.owner_module, output.source) for output in outputs],
            [
                (51, "Virtual_Input_1.monitor"),
                (52, "alsa_input.test.analog-stereo"),
            ],
        )

    def test_parse_sink_inputs(self):
        inputs = parse_sink_inputs(SINK_INPUTS)
        self.assertEqual(
            [(item.owner_module, item.sink_index) for item in inputs],
            [(51, 2), (52, 2)],
        )
        self.assertEqual(inputs[0].label, "Firefox")
        self.assertEqual(inputs[0].identity, "firefox|Music tab")
        self.assertEqual(inputs[0].volume, 100)
        self.assertEqual(inputs[1].channel_map, ("mono",))
        self.assertTrue(inputs[1].muted)


if __name__ == "__main__":
    unittest.main()
