import re
from urllib.request import urlopen
from urllib.parse import urlparse, urlunparse
from xml.etree import ElementTree

from girder import logger, events
from girder.models.setting import Setting

from . import DataONELocations
from ..import_providers import ImportProvider
from ..data_map import DataMap
from ..file_map import FileMap
from ..import_item import ImportItem
from ..entity import Entity
from .dataone_register import D1_lookup, get_package_list
from .dataone_register import \
    extract_metadata_docs, \
    get_documents, \
    extract_data_docs, \
    extract_resource_docs, \
    check_multiple_metadata
from ... import constants

ALL_LOCATIONS = [DataONELocations.prod_cn, DataONELocations.dev_mn, DataONELocations.dev_cn]
# TODO: I'm not sure if search.d.o should be here
ADDITIONAL_LOCATIONS = ['https://search.dataone.org/view/']


class DataOneImportProvider(ImportProvider):
    def __init__(self):
        super().__init__('DataONE')
        events.bind('model.setting.save.after', 'wholetale', self.setting_changed)

    @staticmethod
    def create_regex():
        urls = []
        url = Setting().get(constants.PluginSettings.DATAONE_URL)
        resp = urlopen(url)
        logger.info('[DataONE] using {} to find nodes'.format(url))
        resp_body = resp.read()

        tree = ElementTree.fromstring(resp_body)
        if tree.tag.endswith('nodeList'):
            logger.info('[DataONE] Registering a node list from CN')
            for node in tree.findall('node'):
                node_url = urlparse(node.find('baseURL').text)
                urls.append(urlunparse(node_url._replace(path='')))
        elif tree.tag.endswith('node'):
            logger.info('[DataONE] Registering a single MN')
            node_url = urlparse(tree.find('baseURL').text)
            urls.append(urlunparse(node_url._replace(path='')))

        urls += ADDITIONAL_LOCATIONS
        logger.debug("[DataONE] Found following nodes: " + "; ".join(urls))
        return re.compile("^" + "|".join(urls) + ".*$")

    def setting_changed(self, event):
        if not hasattr(event, "info") or \
                event.info.get('key', '') != constants.PluginSettings.DATAONE_URL:
            return
        self._regex = None

    def lookup(self, entity: Entity) -> DataMap:
        # just wrap D1_lookup for now
        # this does not seem to properly resolve individual files. If passed something like
        # https://cn.dataone.org/cn/v2/resolve/urn:uuid:9266a118-78b3-48e3-a675-b3dfcc5d0fc4,
        # it returns the parent dataset, which, as a user, I'd be annoyed with
        dm = D1_lookup(entity.getValue(), entity['base_url'])
        dm.setRepository(self.getName())
        return dm

    def listFiles(self, entity: Entity) -> FileMap:
        result = get_package_list(entity.getValue(), entity['base_url'])
        return FileMap.fromDict(result)

    def _listRecursive(self, user, pid: str, name: str, base_url: str = DataONELocations.prod_cn,
                       progress=None):
        """Create a package description (Dict) suitable for dumping to JSON."""
        if progress:
            progress.update(increment=1, message='Processing package {}.'.format(pid))

        # query for things in the resource map. At this point, it is assumed that the pid
        # has been correctly identified by the user in the UI.

        docs = get_documents(pid, base_url)

        # Filter the Solr result by TYPE so we can construct the package
        metadata = extract_metadata_docs(docs)
        data = extract_data_docs(docs)
        children = extract_resource_docs(docs)

        # Add in URLs to resolve each metadata/data object by
        self._addResolutionUrls(metadata, base_url)
        self._addResolutionUrls(data, base_url)

        # Determine the folder name. This is usually the title of the metadata file
        # in the package but when there are multiple metadata files in the package,
        # we need to figure out which one is the 'main' or 'documenting' one.
        primary_metadata = [doc for doc in metadata if 'documents' in doc]

        check_multiple_metadata(primary_metadata)

        # Create a Dict to store folders' information
        # the data key is a concatenation of the data and any metadata objects
        # that aren't the main or documenting metadata

        data += [doc for doc in metadata
                 if doc['identifier'] != primary_metadata[0]['identifier']]
        if not name:
            name = primary_metadata[0]['title']

        yield ImportItem(ImportItem.FOLDER, name, identifier=primary_metadata[0]['identifier'])

        for fileObj in data:
            try:
                fileName = fileObj['fileName']
            except KeyError:
                fileName = fileObj['identifier']

            yield ImportItem(ImportItem.FILE, fileName, identifier=fileObj['identifier'],
                             url=fileObj['url'], size=int(fileObj['size']),
                             mimeType=fileObj['formatId'])

        # Recurse and add child packages if any exist
        if children is not None and len(children) > 0:
            for child in children:
                logger.debug('Registering child package, {}'.format(child['identifier']))
                yield from self._listRecursive(progress, user, child['identifier'], base_url)

        yield ImportItem(ImportItem.END_FOLDER)
        logger.debug('Finished registering dataset')

    def _addResolutionUrls(self, list, base_url):
        """
        The download url is different between DataONE production and DataONE dev.
        Check which place we're registering from and set the url section.
        """
        if base_url == DataONELocations.prod_cn:
            url_insert = 'resolve'
        else:
            url_insert = 'object'
        for d in list:
            d['url'] = "{}/{}/{}".format(base_url, url_insert, d['identifier'])
