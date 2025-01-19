from steam.client import SteamClient
from pathlib import Path

import re
import vdf

somnium_app_id = '948740' # AI: Somnium Files
basedir = Path.home() / 'Games' / 'virtual-steam-library'

am_re = re.compile(r"^appmanifest_(\d+).acf$")

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

        metadata = get_metadata_for_appids(appids)

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


def get_metadata_for_appids(appids: list[int]) -> dict[int, str]:
    client = SteamClient()
    client.anonymous_login()
    info = client.get_product_info(apps=appids)
    return info['apps']


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
