# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Copyright (c) 2026 Living Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Licensed under Living Sin Proprietary License (LSPL-1.0)
# See LICENSE file for details.
import json, subprocess, sys, time, os
from pathlib import Path

def _server():
    s = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "control-panel/server.py"), "43128"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    time.sleep(1.5)
    return s

def test_health():
    s = _server()
    try:
        out = subprocess.run(["curl", "-s", "http://127.0.0.1:43128/api/health"], capture_output=True, text=True)
        assert out.returncode == 0
        data = json.loads(out.stdout)
        assert data.get("status") == "ok"
    finally:
        s.terminate()
        s.wait(timeout=5)

def test_index_html():
    s = _server()
    try:
        out = subprocess.run(["curl", "-s", "http://127.0.0.1:43128/"], capture_output=True, text=True)
        assert out.returncode == 0
        assert "<title>Firedragon Control Panel</title>" in out.stdout
    finally:
        s.terminate()
        s.wait(timeout=5)
