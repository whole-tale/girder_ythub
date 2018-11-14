import os
import re
import requests

from urllib.parse import urlparse
from girder.utility.model_importer import ModelImporter

from .import_providers import ImportProvider
from .entity import Entity
from .data_map import DataMap
from .file_map import FileMap


class HTTPImportProvider(ImportProvider):
    def __init__(self):
        super().__init__('HTTP')

    @staticmethod
    def create_regex():
        return re.compile(r'^http(s)?://.*')

    def lookup(self, entity: Entity) -> DataMap:
        pid = entity.getValue()
        url = urlparse(pid)
        if url.scheme not in ('http', 'https'):
            # This should be redundant. This should only be called if matches()
            # returns True, which, various errors aside, signifies a commitment
            # to the entity being legitimate from the perspective of this provider
            raise Exception('Unknown scheme %s' % url.scheme)
        headers = requests.head(pid).headers

        valid_target = headers.get('Content-Type') is not None
        valid_target = valid_target and \
            ('Content-Length' in headers or 'Content-Range' in headers)
        if not valid_target:
            raise Exception('Failed to get size for %s' % pid)

        if 'Content-Disposition' in headers:
            fname = re.search(r'^.*filename=([\w.]+).*$',
                              headers['Content-Disposition'])
            if fname:
                fname = fname.groups()[0]
        else:
            fname = os.path.basename(url.path.rstrip('/'))

        size = headers.get('Content-Length') or \
            headers.get('Content-Range').split('/')[-1]

        return DataMap(pid, int(size), name=fname, repository=self.getName())

    def listFiles(self, entity: Entity) -> FileMap:
        dm = self.lookup(entity)
        if dm is None:
            return None
        else:
            fm = FileMap(dm.getName())
            fm.addFile(entity.getValue(), dm.getSize())
            return fm

    def register(self, parent: object, parentType: str, progress, user, dataMap: DataMap,
                 base_url: str = None):
        url = dataMap.getDataId()
        progress.update(increment=1, message='Processing file {}.'.format(url))
        headers = requests.head(url).headers
        size = headers.get('Content-Length') or \
            headers.get('Content-Range').split('/')[-1]
        fileModel = ModelImporter.model('file')
        fileDoc = fileModel.createLinkFile(
            url=url, parent=parent, name=dataMap.getName(), parentType=parentType,
            creator=user, size=int(size),
            mimeType=headers.get('Content-Type', 'application/octet-stream'),
            reuseExisting=True)
        gc_file = fileModel.filter(fileDoc, user)

        gc_item = ModelImporter.model('item').load(
            gc_file['itemId'], force=True)
        gc_item['meta'] = {'identifier': None, 'provider': 'HTTP'}
        gc_item = ModelImporter.model('item').updateItem(gc_item)
        return ('item', gc_item)
