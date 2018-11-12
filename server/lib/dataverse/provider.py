import json
import re
from urllib.parse import urlparse, urlunparse
from urllib.request import urlopen

from ..import_providers import ImportProvider
from ..data_map import DataMap
from ..file_map import FileMap
from ..import_item import ImportItem
from ..entity import Entity


# Url returning json that contains all active Dataverse instances
_INSTALLATIONS_URL = 'https://services.dataverse.harvard.edu/miniverse/map/installations-json'


class DataverseImportProvider(ImportProvider):
    def __init__(self):
        super().__init__('Dataverse')
        self._get_dataverse_installations()

    def _get_dataverse_installations(self):
        resp = urlopen(_INSTALLATIONS_URL).read()
        data = json.loads(resp.decode('utf-8'))
        urls = [_['url'] for _ in data['installations']]
        self.regex_dataverse = re.compile("^" + "|".join(urls) + ".*$")

    def matches(self, entity: Entity) -> bool:
        url = entity.getValue()
        return self.regex_dataverse.match(url) is not None

    @staticmethod
    def _parse_dataset(pid: str):
        url = urlunparse(
            urlparse(pid)._replace(path='/api/datasets/:persistentId')
        )
        resp = urlopen(url).read()
        data = json.loads(resp.decode('utf-8'))
        meta = data['data']['latestVersion']['metadataBlocks']['citation']['fields']
        title = next(_['value'] for _ in meta if _['typeName'] == 'title')
        doi = '{authority}/{identifier}'.format(**data['data'])
        files = data['data']['latestVersion']['files']
        return title, files, doi

    def lookup(self, entity: Entity) -> DataMap:
        title, files, doi = self._parse_dataset(entity.getValue())
        size = sum(_['dataFile']['filesize'] for _ in files)
        return DataMap(entity.getValue(), size, doi=doi, name=title,
                       repository=self.getName())

    def listFiles(self, entity: Entity) -> FileMap:
        stack = []
        top = None
        for item in self._listRecursive(entity.getUser(), entity.getValue()):
            if item.type == ImportItem.FOLDER:
                if len(stack) == 0:
                    fm = FileMap(item.name)
                else:
                    fm = stack[-1].addChild(item.name)
                stack.append(fm)
            elif item.type == ImportItem.END_FOLDER:
                top = stack.pop()
            elif item.type == ImportItem.FILE:
                stack[-1].addFile(item.name, item.size)
        return top

    def _listRecursive(self, user, pid: str, name: str, base_url: str = None,
                       progress=None):
        """Create a package description (Dict) suitable for dumping to JSON."""
        title, files, _ = self._parse_dataset(pid)
        access_url = urlunparse(
            urlparse(pid)._replace(path='/api/access/datafile', query='')
        )
        yield ImportItem(ImportItem.FOLDER, name=title)
        for obj in files:
            yield ImportItem(
                ImportItem.FILE, obj['dataFile']['filename'],
                size=obj['dataFile']['filesize'],
                mimeType='application/octet-stream',
                url=access_url + '/' + str(obj['dataFile']['id'])
            )
        yield ImportItem(ImportItem.END_FOLDER)
