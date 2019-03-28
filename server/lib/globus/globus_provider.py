import os
import re
from typing import Tuple
from html.parser import HTMLParser
from urllib.parse import parse_qs
from urllib.request import OpenerDirector, HTTPSHandler

from girder.models.item import Item
from girder.models.folder import Folder

from plugins.wholetale.server.lib.file_map import FileMap
from ..import_providers import ImportProvider
from ..resolvers import DOIResolver
from ..entity import Entity
from ..data_map import DataMap
from ..import_item import ImportItem

from girder.plugins.globus_handler.clients import Clients


class GlobusImportProvider(ImportProvider):
    def __init__(self):
        super().__init__('Globus')
        self.clients = Clients()

    @staticmethod
    def create_regex():
        return re.compile(r'^https://publish.globus.org/jspui/handle/.*')

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
        yield ImportItem(ImportItem.FOLDER, name=title, identifier='doi:' + doi)
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

    def getDatasetUID(self, doc, user):
        if 'folderId' in doc:
            path_to_root = Item().parentsToRoot(doc, user=user)
        else:
            path_to_root = Folder().parentsToRoot(doc, user=user)
        # Collection{WT Catalog} / Folder{WT Catalog} / Folder{Globus ds root}
        return path_to_root[2]['object']['meta']['identifier']

    def getURI(self, doc, user):
        if 'folderId' in doc:
            fileObj = Item().childFiles(doc)[0]
            return fileObj['linkUrl']
        else:
            path_to_root = Folder().parentsToRoot(doc, user=user)
            root_folder = path_to_root[2]
            # There's always 'globus_metadata.json'...
            item = Folder().childItems(root_folder['object'], user=user)[0]
            fileObj = Item().childFiles(item)[0]
            root_path = os.path.dirname(fileObj['linkUrl'])
            for path in path_to_root[3:]:
                root_path = os.path.join(root_path, path['object']['name'])
            return os.path.join(root_path, doc['name'])


TRANSFER_URL_PREFIX = 'https://app.globus.org/file-manager?'


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
