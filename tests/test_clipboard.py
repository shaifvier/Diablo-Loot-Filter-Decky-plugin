import os
import tempfile
import unittest
from pathlib import Path

from backend.clipboard import discover_sessions


class DiscoveryTest(unittest.TestCase):
    def test_nonsteamlaunchers_game_display_takes_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for pid, comm, display in [(1, "steam", ":0"), (2, "Diablo IV.exe", ":1"), (3, "steamwebhelper", ":0")]:
                process = root / str(pid)
                process.mkdir()
                (process / "comm").write_text(comm)
                (process / "environ").write_text(f"DISPLAY={display}\0STEAM_COMPAT_DATA_PATH=/steamapps/compatdata/NonSteamLaunchers\0")
            sessions = discover_sessions(root)
            self.assertEqual([s["display"] for s in sessions], [":1", ":0"])
            self.assertTrue(sessions[0]["game"])

    def test_shared_steam_game_display_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for pid, comm in [(1, "steam"), (2, "Diablo IV.exe")]:
                process = root / str(pid)
                process.mkdir()
                (process / "comm").write_text(comm)
                (process / "environ").write_text("DISPLAY=:0\0")
            self.assertEqual(discover_sessions(root), [{"display": ":0", "auth": None, "game": True}])

    def test_remote_display_and_other_users_are_not_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            process = Path(directory) / "1"
            process.mkdir()
            (process / "comm").write_text("Diablo IV.exe")
            (process / "environ").write_text("DISPLAY=example.org:0\0")
            sessions = discover_sessions(Path(directory), uid=os.getuid() + 1)
            self.assertFalse(any(s["game"] for s in sessions))


if __name__ == "__main__":
    unittest.main()
