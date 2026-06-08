#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Launch the app from the project virtual environment.
source "$APP_DIR/.venv/bin/activate"
exec python "$APP_DIR/wifi_scanner.py"
