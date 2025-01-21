from steam.client import SteamClient
from pathlib import Path
from time import time
from xdg import BaseDirectory

import json
import random
import re
import vdf


RESOURCE_NAME = 'gg.kekemui.steam-linker'
basedir = Path.home() / 'Games' / 'virtual-steam-library'

am_re = re.compile(r"^appmanifest_(\d+).acf$")

class Directories:
    cacheDir = Path(BaseDirectory.save_cache_path(RESOURCE_NAME))
    configDir = Path(BaseDirectory.save_config_path(RESOURCE_NAME))

class Library:
    # basepath: Path
    # games: list['Game']
    # gamefiles: Path
    # compatdata: Path
    # shadercache: Path

    def __init__(self, basepath: Path):
        self.basepath = basepath / 'steamapps'
        self.gamefiles = self.basepath / 'common'
        self.compatdata = self.basepath / 'compatdata'
        self.shadercache = self.basepath / 'shadercache'

    def build_games(self):
        matches = list(am_re.match(x.name) for x in self.basepath.iterdir())
        appids = list(int(x.groups()[0]) for x in matches if x)

        dl = DataLookup()

        metadata = dl.get_metadata_for_appids(appids)

        self.games = list(Game(library=self, metadata=value) for value in metadata.values() if 'game' == value['common']['type'].casefold())


class Game:
    # appid: str
    # name: str
    # installdir: str
    # parent: Library

    # gamedata: Path | None
    # compatdata: Path | None
    # native_config_data: Path | None # unused for now, needs discrete overrides

    def __init__(self, library: Library, metadata: dict):
        # print(metadata)
        self.appid = metadata['appid']
        self.name = metadata['common']['name']
        self.installdir = metadata['config']['installdir']
        self.parent = library

        self.gamedata = self.parent.gamefiles / self.installdir

        compatdata: Path = self.parent.compatdata / str(self.appid)
        if compatdata.is_dir():
            self.compatdata = compatdata
        else:
            self.compatdata = None

    def make_symlink_farm(self):
        print(f"Building symlink farm for {self.appid}: {self.name}")
        dest = basedir / self.installdir

        if dest.is_dir():
            print(f"{self.name} already has a symlink, continuing")
            return
        
        dest.mkdir(parents=True, exist_ok=False)
        gd_link = dest / 'gamedata'
        gd_link.symlink_to(self.gamedata)

        if self.compatdata:
            cd_link = dest / 'compatdata'
            cd_link.symlink_to(self.compatdata)

    def __str__(self):
        return f"({self.appid=}; {self.name=})"


class DataLookup:
    CACHE_TTL_SECONDS = 60 * 60 * 24 * 14
    CACHE_TTL_VARIANCE = 60 * 60 * 24 * 1

    def __init__(self):
        self.client = SteamClient()
        self.client.anonymous_login()
        
    def get_metadata_for_appids(self, appids: list[int]) -> dict[int, dict]:
        cached_results = {}
        for appid in appids:
            cached = self.__get_cached_metadata_for_appid(appid)
            if cached is not None:
                cached_results[appid] = cached

        missing_appids = list(appid for appid in appids if appid not in cached_results.keys())

        if missing_appids:
            live_results = self.client.get_product_info(missing_appids)['apps']
        else:
            live_results = {}
        self.__write_cache_entries(live_results)
        return cached_results | live_results

    def __get_cached_metadata_for_appid(self, appid: int, ignore_ttl: bool = False) -> dict|None:
        cache_path = DataLookup._get_cache_path_for_appid(appid)
        if not cache_path.exists():
            print(f"Cache miss for {appid}")
            return None

        effective_cache_ttl = DataLookup.CACHE_TTL_SECONDS + random.randrange(-DataLookup.CACHE_TTL_VARIANCE, DataLookup.CACHE_TTL_VARIANCE)
        modtime = cache_path.stat().st_mtime
        expiration_seconds = modtime + effective_cache_ttl
        now = time()
        if ignore_ttl or (expiration_seconds < now):
            print(f"Calculated expiry time {expiration_seconds} is before {now=}, ignoring")
            return None

        print(f"Cache hit for {appid}")
        return json.loads(cache_path.read_text())

    def __write_cache_entries(self, metadata: dict[int, dict]):
        for (key, value) in metadata.items():
            DataLookup._get_cache_path_for_appid(key).write_text(json.dumps(value))
            print(f"Wrote cache for {key}")

    def _get_cache_path_for_appid(appid: int) -> Path:
        return Directories.cacheDir / f"{appid}.json"


def get_libraries() -> list[Library]:
    with open(Path.home() / '.steam' / 'steam' / 'config'/ 'libraryfolders.vdf') as libvdf:
        libraries = vdf.load(libvdf)
    libs = []
    for lib in libraries['libraryfolders'].values():
        path = Path(lib['path'])
        if path.is_dir():
            libs.append(Library(path))
    return libs


def main():
    libs = get_libraries()
    
    games: list[Game] = []
    for lib in libs:
        lib.build_games()
        games = games + lib.games

    for game in games:
        game.make_symlink_farm()


if __name__ == "__main__":
    main()
