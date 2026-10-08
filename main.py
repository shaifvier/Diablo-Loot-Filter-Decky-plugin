import asyncio
import sys
from pathlib import Path

import decky

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend.clipboard import Clipboard
from backend.service import LootService


class Plugin:
    async def _main(self):
        self._initialize()
        decky.logger.info("Diablo Loot Filters ready")

    def _initialize(self):
        if not hasattr(self, "service"):
            self.service = LootService(Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / "cache")
            self.clipboard = Clipboard(Path(__file__).parent / "bin" / "d4-clipboard",
                                       uid=Path(decky.DECKY_USER_HOME).stat().st_uid)

    async def _call(self, method, *args):
        self._initialize()
        try:
            result = await asyncio.to_thread(method, *args)
            return {"ok": True, "data": result}
        except (ValueError, OSError, KeyError, TypeError) as exc:
            decky.logger.warning("Loot filter request failed: %s", type(exc).__name__)
            return {"ok": False, "error": str(exc) if isinstance(exc, ValueError) else "The provider data could not be read. Refresh and retry."}

    async def list_filters(self, refresh=False):
        self._initialize()
        return await self._call(self.service.list_filters, refresh)

    async def get_filter(self, filter_id):
        self._initialize()
        return await self._call(self.service.get_filter, filter_id)

    async def load_build(self, url):
        self._initialize()
        return await self._call(self.service.load_build, url)

    async def generate_filter(self, build_id, variant_id, strict=False, name=None):
        self._initialize()
        return await self._call(self.service.generate_filter, build_id, variant_id, strict, name)

    async def copy_filter(self, filter_id):
        self._initialize()
        def copy():
            record = self.service.get_filter(filter_id)
            return self.clipboard.copy(record["code"])
        return await self._call(copy)

    async def _unload(self):
        if hasattr(self, "clipboard"):
            await asyncio.to_thread(self.clipboard.close)

    async def _uninstall(self):
        await self._unload()

    async def _migration(self):
        pass
