from typing import Tuple
from html.parser import HTMLParser
from urllib.parse import parse_qs
from urllib.request import OpenerDirector, HTTPSHandler

from ..import_providers import ImportProvider
from ..resolvers import DOIResolver
from ..entity import Entity
from ..data_map import DataMap

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
        size = self._computeSize(endpoint, path, entity.getUser())
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

    def _computeSize(self, endpoint, path, user):
        tc = self.clients.getUserTransferClient(user)
        return self._computeSizeRec(tc, endpoint, '/~/%s' % path)

    def _computeSizeRec(self, tc, endpoint, path):
        sz = 0
        for entry in tc.operation_ls(endpoint, path=path):
            if entry['type'] == 'dir':
                sz = sz + self._computeSizeRec(tc, endpoint, path + '/' + entry['name'])
            elif entry['type'] == 'file':
                sz = sz + entry['size']
        return sz


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
