"""Check startup scheduling and preference preservation without Kodi/network."""
import importlib.util
from pathlib import Path
import tempfile
import json

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('startup_updates', HERE / 'overlay/resources/lib/startup_updates.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Store:
    def __init__(self, path): self.root = str(path)
    def read(self, path, default):
        return json.loads(Path(path).read_text()) if Path(path).exists() else default
    def write(self, path, data): Path(path).write_text(json.dumps(data))

class Addon:
    disabled = False
    def getSetting(self, name): return 'false' if self.disabled else 'true'
    def getAddonInfo(self, name): return '0.10.5'

class Player:
    playing = False
    def isPlaying(self): return self.playing

with tempfile.TemporaryDirectory(dir=HERE.parents[1] / 'outputs') as tmp:
    store, addon, player, calls = Store(tmp), Addon(), Player(), []
    now, online = [0.0], [False]
    make = lambda: module.StartupUpdates(store, addon, calls.append,
                                       lambda: online[0], lambda: now[0],
                                       lambda: now[0] + 10000)
    check = make(); check.poll(player); assert not calls
    now[0] = 31; check.poll(player); assert not calls
    online[0] = True; player.playing = True; check.poll(player); assert not calls
    player.playing = False; check.poll(player, installing=True); assert not calls
    check.poll(player); check.poll(player); assert calls == ['UpdateAddonRepos']
    restart = make(); now[0] += 31; restart.poll(player); assert len(calls) == 1
    now[0] += 400; later = make(); now[0] += 31; later.poll(player); assert len(calls) == 2
    addon.disabled = True; off = make(); now[0] += 31; off.poll(player); assert len(calls) == 2
    addon.disabled = False; offline = make(); online[0] = False; now[0] += 301
    offline.poll(player); assert offline.done and len(calls) == 2
print('Startup: delay, idle/setup/network guards, single check, restart cooldown, opt-out and timeout passed.')
