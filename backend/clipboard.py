"""Copy to the actual game and Steam Xwayland sessions, independent of app IDs."""
import os
import re
import select
import subprocess
import threading
from pathlib import Path

from .codec import decode_filter


def discover_sessions(proc_root=Path("/proc"), uid=None):
    uid = os.getuid() if uid is None else uid
    sessions = []
    for path in proc_root.iterdir():
        if not path.name.isdigit():
            continue
        try:
            if path.stat().st_uid != uid:
                continue
            comm = (path / "comm").read_text().strip().lower()
            if comm not in ("diablo iv.exe", "steam", "steamwebhelper"):
                continue
            env = dict(v.split("=", 1) for v in (path / "environ").read_text().split("\0") if "=" in v)
            display = env.get("DISPLAY", "")
            if not re.fullmatch(r":\d+(?:\.\d+)?", display):
                continue
            auth = env.get("XAUTHORITY")
            if auth and not Path(auth).is_file():
                # Proton's pressure-vessel Xauthority lives in its mount namespace.
                candidate = path / "root" / auth.lstrip("/")
                auth = str(candidate) if candidate.is_file() else None
            sessions.append({"display": display, "auth": auth,
                             "game": comm == "diablo iv.exe"})
        except (OSError, ValueError):
            continue
    # Prefer the game process's authentication when both share a display.
    unique = {}
    for session in sorted(sessions, key=lambda s: s["game"], reverse=True):
        unique.setdefault(session["display"], session)
    if not unique:
        display = os.environ.get("DISPLAY", "")
        if re.fullmatch(r":\d+(?:\.\d+)?", display):
            unique[display] = {"display": display, "auth": os.environ.get("XAUTHORITY"), "game": False}
    return list(unique.values())[:5]


class Clipboard:
    def __init__(self, binary, uid=None):
        self.binary = Path(binary)
        self.uid = uid
        self.processes = {}
        self.lock = threading.Lock()

    def copy(self, code):
        decode_filter(code)
        if not self.binary.is_file():
            raise ValueError("Clipboard helper is missing. Reinstall the plugin ZIP.")
        with self.lock:
            sessions = discover_sessions(uid=self.uid)
            copied, failed = [], []
            for session in sessions:
                display = session["display"]
                env = os.environ.copy()
                env["DISPLAY"] = display
                env.pop("XAUTHORITY", None)
                if session["auth"]:
                    env["XAUTHORITY"] = session["auth"]
                process = subprocess.Popen([str(self.binary), display], stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           env=env, start_new_session=True)
                try:
                    process.stdin.write(code.encode("ascii"))
                    process.stdin.close()
                    ready, _, _ = select.select([process.stdout], [], [], 3)
                    if not ready or process.stdout.readline().strip() != b"READY":
                        raise ValueError("Game clipboard display could not be opened.")
                    old = self.processes.get(display)
                    self.processes[display] = process
                    if old and old.poll() is None:
                        old.terminate()
                    if old:
                        old.wait(timeout=2)
                    copied.append(display)
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    process.kill()
                    process.wait()
                    failed.append(display)
                finally:
                    process.stdout.close()
                    process.stderr.close()
            detected = any(s["game"] for s in sessions)
            game_copied = any(s["game"] and s["display"] in copied for s in sessions)
            return {"copied": bool(copied), "gameDetected": detected, "gameCopied": game_copied,
                    "displays": copied, "error": ("Could not access displays: " + ", ".join(failed)) if failed else
                    ("No local game or Steam display was found." if not copied else None)}

    def close(self):
        with self.lock:
            for process in self.processes.values():
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=3)
            self.processes.clear()
