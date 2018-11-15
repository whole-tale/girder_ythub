import json
import re
import os
from urllib.parse import urlparse, urlunparse, parse_qs
from urllib.request import urlopen

from girder import events
from girder.models.setting import Setting

from ..import_providers import ImportProvider
from ..data_map import DataMap
from ..file_map import FileMap
from ..import_item import ImportItem
from ..entity import Entity
from ... import constants

_DOI_REGEX = re.compile(r'(10.\d{4,9}/[-._;()/:A-Z0-9]+)', re.IGNORECASE)
_QUOTES_REGEX = re.compile(r'"(.*)"')


def _query_dataverse(search_url):
    resp = urlopen(search_url).read()
    data = json.loads(resp.decode('utf-8'))['data']
    if data['count_in_response'] != 1:
        raise ValueError
    item = data['items'][0]
    files = [{
        'dataFile': {
            'filename': item['name'],
            'mimeType': item['file_content_type'],
            'filesize': item['size_in_bytes'],
            'id': item['file_id']
        }
    }]
    title = item['name']
    title_search = _QUOTES_REGEX.search(item['dataset_citation'])
    if title_search is not None:
        title = title_search.group().strip('"')
    doi = None
    doi_search = _DOI_REGEX.search(item['dataset_citation'])
    if doi_search is not None:
        doi = doi_search.group()
    return title, files, doi


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
    def _parse_dataset(url):
        """Extract title, file, doi from Dataverse resource.

        Handles: {siteURL}/dataset.xhtml?persistentId={persistentId}
        """
        url = urlunparse(
            url._replace(path='/api/datasets/:persistentId')
        )
        resp = urlopen(url).read()
        data = json.loads(resp.decode('utf-8'))
        meta = data['data']['latestVersion']['metadataBlocks']['citation']['fields']
        title = next(_['value'] for _ in meta if _['typeName'] == 'title')
        doi = '{authority}/{identifier}'.format(**data['data'])
        files = data['data']['latestVersion']['files']
        return title, files, doi

    @staticmethod
    def _parse_file_url(url):
        """Extract title, file, doi from Dataverse resource.

        Handles: {siteURL}/file.xhtml?persistentId={persistentId}&...
        """
        qs = parse_qs(url.query)
        try:
            full_doi = qs['persistentId'][0]
        except (KeyError, ValueError):
            # fail here in a meaningful way...
            raise

        file_persistent_id = os.path.basename(full_doi)
        doi = os.path.dirname(full_doi)
        if doi.startswith('doi:'):
            doi = doi[4:]

        search_url = urlunparse(
            url._replace(path='/api/search', query='q=filePersistentId:' + file_persistent_id)
        )
        title, files, _ = _query_dataverse(search_url)
        return title, files, doi

    @staticmethod
    def _parse_access_url(url):
        """Extract title, file, doi from Dataverse resource.

        Handles: {siteURL}/api/access/datafile/{fileId}
        """
        fileId = os.path.basename(url.path)
        search_url = urlunparse(
            url._replace(path='/api/search', query='q=entityId:' + fileId)
        )
        return _query_dataverse(search_url)

    def parse_pid(self, pid: str):
        url = urlparse(pid)
        if url.path.endswith('file.xhtml'):
            return self._parse_file_url(url)
        elif url.path.startswith('/api/access/datafile'):
            return self._parse_access_url(url)
        else:
            return self._parse_dataset(url)

    def lookup(self, entity: Entity) -> DataMap:
        title, files, doi = self.parse_pid(entity.getValue())
        size = sum(_['dataFile']['filesize'] for _ in files)
        return DataMap(entity.getValue(), size, doi=doi, name=title,
                       repository=self.getName())

    def listFiles(self, entity: Entity) -> FileMap:
        stack = []
        top = None
        for item in self._listRecursive(entity.getUser(), entity.getValue(), None):
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
        title, files, _ = self.parse_pid(pid)
        access_url = urlunparse(
            urlparse(pid)._replace(path='/api/access/datafile', query='')
        )
        yield ImportItem(ImportItem.FOLDER, name=title)
        for obj in files:
            yield ImportItem(
                ImportItem.FILE, obj['dataFile']['filename'],
                size=obj['dataFile']['filesize'],
                mimeType=obj['dataFile'].get('mimeType', 'application/octet-stream'),
                url=access_url + '/' + str(obj['dataFile']['id'])
            )
        yield ImportItem(ImportItem.END_FOLDER)
