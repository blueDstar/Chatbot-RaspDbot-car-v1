#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

# Kích hoạt venv
source "$APP_DIR/.venv/bin/activate"
python "$APP_DIR/gtk_raspbot_app.py"

# (Tuỳ chọn) ép model mặc định:
# export DEFAULT_MODEL="raspdbot-car.Q4_K_M.gguf"
# export DEFAULT_MODEL="raspdbot-star.Q4_K_M.gguf"

