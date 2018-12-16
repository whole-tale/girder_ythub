from typing import Tuple
from html.parser import HTMLParser
from urllib.parse import parse_qs
from urllib.request import OpenerDirector, HTTPSHandler

from plugins.wholetale.server.lib.file_map import FileMap
from ..import_providers import ImportProvider
from ..resolvers import DOIResolver
from ..entity import Entity
from ..data_map import DataMap
from ..import_item import ImportItem

from girder.plugins.wt_data_manager.lib.handlers._globus.clients import Clients


class GlobusImportProvider(ImportProvider):
    def __init__(self):
        super().__init__('Globus')
        self.clients = Clients()

    def matches(self, entity: Entity) -> bool:
        return entity.getValue().startswith('https://publish.globus.org/jspui/handle/')

    def lookup(self, entity: Entity) -> DataMap:
        doc = self._getDocument(entity.getValue())
        (endpoint, path, doi, title) = self._extractMeta(doc)
        self.clients.getUserTransferClient(entity.getUser())
        # Don't compute size here. The recursive traversal of typical directory structures
        # in a datase takes ages and we want the lookup method to quickly identify whether
        # a repository has a dataset or not.
        # size = self._computeSize(tc, endpoint, path, entity.getUser())
        size = -1
        return DataMap(entity.getValue(), size, doi=doi, name=title, repository=self.getName())

    def _getDocument(self, url):
        od = OpenerDirector()
        od.add_handler(HTTPSHandler())
        with od.open(url) as resp:
            if resp.status == 200:
                return resp.read().decode('utf-8')
            elif resp.status == 404:
                raise Exception('Document not found %s' % url)
            else:
                raise Exception('Error fetching document %s: %s' % (url, resp.read()))

    def _extractMeta(self, doc) -> Tuple[str, str, str, str]:
        dp = DocParser()
        dp.feed(doc)
        return dp.getMeta()

    def _computeSize(self, tc, endpoint, path, user):
        sz = 0
        for item in self._listRecursive2(tc, endpoint, path):
            if item.type == ImportItem.FILE:
                sz += item.size
        return sz

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

    def _listRecursive(self, user, pid: str, name: str, base_url: str = None, progress=None):
        doc = self._getDocument(pid)
        (endpoint, path, doi, title) = self._extractMeta(doc)
        yield ImportItem(ImportItem.FOLDER, name=title)
        tc = self.clients.getUserTransferClient(user)
        yield from self._listRecursive2(tc, endpoint, path, progress)
        yield ImportItem(ImportItem.END_FOLDER)

    def _listRecursive2(self, tc, endpoint: str, path: str, progress=None):
        if path[-1] != '/':
            path = path + '/'
        if progress:
            progress.update(increment=1, message='Listing files')
        for entry in tc.operation_ls(endpoint, path=path):
            if entry['type'] == 'dir':
                yield ImportItem(ImportItem.FOLDER, name=entry['name'])
                yield from self._listRecursive2(tc, endpoint, path + entry['name'], progress)
                yield ImportItem(ImportItem.END_FOLDER)
            elif entry['type'] == 'file':
                yield ImportItem(
                    ImportItem.FILE, entry['name'], size=entry['size'],
                    mimeType='application/octet-stream',
                    url='globus://%s/%s%s' % (endpoint, path, entry['name']))


TRANSFER_URL_PREFIX = 'https://www.globus.org/app/transfer?'


class DocParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = None
        self.doi = None
        self.endpoint = None
        self.path = None

    def handle_starttag(self, tag, attrs):
        if tag == 'meta':
            self._handleMetaTag(dict(attrs))
        elif tag == 'a':
            self._handleLink(dict(attrs))

    def _handleMetaTag(self, attrs):
        if 'name' not in attrs:
            return
        if attrs['name'] == 'DC.title':
            self.title = attrs['content']
        elif attrs['name'] == 'DC.identifier':
            self.doi = self._extractDOI(attrs['content'])

    def _extractDOI(self, content):
        return DOIResolver.extractDOI(content)

    def _handleLink(self, attrs):
        if 'href' not in attrs:
            return
        if attrs['href'].startswith(TRANSFER_URL_PREFIX):
            d = parse_qs(attrs['href'][len(TRANSFER_URL_PREFIX):])
            self.endpoint = d['origin_id'][0]
            self.path = d['origin_path'][0]

    def getMeta(self):
        return (self.endpoint, self.path, self.doi, self.title)
