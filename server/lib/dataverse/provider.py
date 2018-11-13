import json
import re
from urllib.parse import urlparse, urlunparse
from urllib.request import urlopen

from girder import events
from girder.models.setting import Setting

from ..import_providers import ImportProvider
from ..data_map import DataMap
from ..file_map import FileMap
from ..import_item import ImportItem
from ..entity import Entity
from ... import constants


class DataverseImportProvider(ImportProvider):
    _dataverse_regex = None

    def __init__(self):
        super().__init__('Dataverse')
        events.bind('model.setting.save.after', 'wholetale', self.setting_changed)

    @property
    def dataverse_regex(self):
        if not self._dataverse_regex:
            self._dataverse_regex = self.create_dataverse_regex()
        return self._dataverse_regex

    @staticmethod
    def get_base_url_setting():
        return Setting().get(constants.PluginSettings.DATAVERSE_URL)

    def create_dataverse_regex(self):
        resp = urlopen(self.get_base_url_setting())
        resp_body = resp.read()
        data = json.loads(resp_body.decode('utf-8'))
        urls = [_['url'] for _ in data['installations']]
        return re.compile("^" + "|".join(urls) + ".*$")

    def setting_changed(self, event):
        if not hasattr(event, "info") or \
                event.info.get('key', '') != constants.PluginSettings.DATAVERSE_URL:
            return
        self._dataverse_regex = None

    def matches(self, entity: Entity) -> bool:
        url = entity.getValue()
        return self.dataverse_regex.match(url) is not None

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
