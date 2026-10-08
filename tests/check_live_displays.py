"""Exercise X11 transfer on host displays without changing the user's clipboard.

Uses a private selection and an independent ctypes reader; no game input.
"""
import ctypes as c
import select
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.clipboard import discover_sessions
from backend.providers import parse_catalog_chunk


class SelectionEvent(c.Structure):
    _fields_ = [("type", c.c_int), ("serial", c.c_ulong), ("send_event", c.c_int),
                ("display", c.c_void_p), ("requestor", c.c_ulong), ("selection", c.c_ulong),
                ("target", c.c_ulong), ("property", c.c_ulong), ("time", c.c_ulong)]


class Event(c.Union):
    _fields_ = [("type", c.c_int), ("selection", SelectionEvent), ("pad", c.c_long * 24)]


def read_selection(display, selection, target):
    lib = c.CDLL("libX11.so.6")
    signatures = {
        "XOpenDisplay": ([c.c_char_p], c.c_void_p),
        "XDefaultRootWindow": ([c.c_void_p], c.c_ulong),
        "XCreateSimpleWindow": ([c.c_void_p, c.c_ulong, c.c_int, c.c_int, c.c_uint, c.c_uint, c.c_uint, c.c_ulong, c.c_ulong], c.c_ulong),
        "XInternAtom": ([c.c_void_p, c.c_char_p, c.c_int], c.c_ulong),
        "XConvertSelection": ([c.c_void_p, c.c_ulong, c.c_ulong, c.c_ulong, c.c_ulong, c.c_ulong], c.c_int),
        "XFlush": ([c.c_void_p], c.c_int),
        "XCheckTypedEvent": ([c.c_void_p, c.c_int, c.POINTER(Event)], c.c_int),
        "XGetWindowProperty": ([c.c_void_p, c.c_ulong, c.c_ulong, c.c_long, c.c_long, c.c_int, c.c_ulong,
                               c.POINTER(c.c_ulong), c.POINTER(c.c_int), c.POINTER(c.c_ulong), c.POINTER(c.c_ulong), c.POINTER(c.c_void_p)], c.c_int),
        "XFree": ([c.c_void_p], c.c_int),
        "XDestroyWindow": ([c.c_void_p, c.c_ulong], c.c_int),
        "XCloseDisplay": ([c.c_void_p], c.c_int),
    }
    for name, (args, result) in signatures.items():
        function = getattr(lib, name)
        function.argtypes, function.restype = args, result
    connection = lib.XOpenDisplay(display.encode())
    if not connection:
        raise RuntimeError("Display unavailable: " + display)
    window = lib.XCreateSimpleWindow(connection, lib.XDefaultRootWindow(connection), 0, 0, 1, 1, 0, 0, 0)
    try:
        atom = lambda name: lib.XInternAtom(connection, name.encode(), 0)
        property_id = atom("D4_DECKY_TEST_RESULT")
        lib.XConvertSelection(connection, atom(selection), atom(target), property_id, window, 0)
        lib.XFlush(connection)
        event = Event()
        deadline = time.monotonic() + 3
        while not lib.XCheckTypedEvent(connection, 31, c.byref(event)):
            if time.monotonic() > deadline:
                raise RuntimeError("Selection request timed out")
            time.sleep(0.02)
        if not event.selection.property:
            raise RuntimeError("Selection target was rejected")
        actual, format_, count, after, data = c.c_ulong(), c.c_int(), c.c_ulong(), c.c_ulong(), c.c_void_p()
        status = lib.XGetWindowProperty(connection, window, property_id, 0, 128000, 1, 0,
                                        c.byref(actual), c.byref(format_), c.byref(count), c.byref(after), c.byref(data))
        if status or format_.value != 8 or after.value:
            raise RuntimeError("Invalid selection property")
        try:
            return c.string_at(data, count.value).decode()
        finally:
            lib.XFree(data)
    finally:
        lib.XDestroyWindow(connection, window)
        lib.XCloseDisplay(connection)


def main():
    root = Path(__file__).resolve().parents[1]
    code = parse_catalog_chunk((root / "tests/fixtures/catalog-chunk.js").read_text())[0]["importCode"]
    sessions = discover_sessions()
    assert sessions, "No local Steam or Diablo sessions"
    for session in sessions:
        display = session["display"]
        owner = subprocess.Popen([str(root / "out/d4-clipboard"), display, "D4_DECKY_TEST"],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            owner.stdin.write(code.encode())
            owner.stdin.close()
            ready, _, _ = select.select([owner.stdout], [], [], 3)
            assert ready and owner.stdout.readline().strip() == b"READY"
            time.sleep(0.25)
            for target in ["UTF8_STRING", "STRING"]:
                assert read_selection(display, "D4_DECKY_TEST", target) == code
            print("Passed persistent UTF8/STRING transfer on", display, "game:", session["game"])
        finally:
            owner.terminate()
            owner.wait(timeout=3)
            owner.stdout.close()
            owner.stderr.close()


if __name__ == "__main__":
    main()
