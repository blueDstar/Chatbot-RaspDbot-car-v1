# RaspDbot-Car Chatbot (GTK4 Desktop App)

A lightweight **Ubuntu desktop chatbot** built with **GTK4 (PyGObject)** and **llama-cpp-python** to run **GGUF models locally** (offline).  
It provides a responsive chat UI (LLM runs in a background thread), a **model picker** that scans `*.gguf` files in the project folder, and **persistent chat history** with load/save/export actions.

## Features

- GTK4 desktop UI (Ubuntu)
- Runs **GGUF** models locally via `llama-cpp-python` (offline)
- **Model selector** (dropdown, auto-scans `*.gguf` in the project directory)
**Chat history**
  - Auto-saves to `~/.local/share/raspdbot/history.json`
  - Menu actions: New chat / Load history / Save history / Export as text
- Assistant speaks as **“I”** and addresses the user as **“you”**
- Safeguards to reduce hallucinated telemetry and multi-turn self-dialogue (stop tokens + output cleanup)

---

## Requirements

- Ubuntu Desktop 24.04 (recommended)
- Python 3.12
- GTK4 + PyGObject (installed via `apt`)
- One or more `.gguf` model files (e.g. `raspdbot-car.Q4_K_M.gguf`, `raspdbot-star.Q4_K_M.gguf`)

---

## Project Layout

Keep these files in the same folder:

```text
RaspDbot/
├─ gtk_raspdbot_app.py
├─ raspdbot_bot.py
├─ run.sh
├─ requirements.txt
├─ raspdbot-car.Q4_K_M.gguf
└─ raspdbot-star.Q4_K_M.gguf
