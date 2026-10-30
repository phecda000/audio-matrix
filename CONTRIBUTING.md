# Contributing

Thanks for improving Audio Matrix.

## Development

1. Install the runtime dependencies described in `README.md`.
2. Make changes under `src/audio_matrix`.
3. Run the test suite:

   ```bash
   PYTHONPATH=src python3 -m unittest discover -s tests -v
   ```

4. Test the app on PulseAudio before opening a pull request:

   ```bash
   ./bin/audio-matrix
   ```

Please keep the user interface readable, avoid unnecessary PulseAudio modules, and clean up modules created by the application.
