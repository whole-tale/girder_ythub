from girder import logger
from girder.utility.model_importer import ModelImporter

from ..import_providers import ImportProvider
from ..data_map import DataMap
from ..file_map import FileMap
from ..entity import Entity
from .dataone_register import D1_lookup, get_package_list
from .dataone_register import \
    extract_metadata_docs, \
    get_documents, \
    extract_data_docs, \
    extract_resource_docs, \
    check_multiple_metadata
from ...constants import DataONELocations

ALL_LOCATIONS = [DataONELocations.prod_cn, DataONELocations.dev_mn, DataONELocations.dev_cn]
ALL_LOCATIONS_2 = ['https://knb.ecoinformatics.org/#view/', 'https://search.dataone.org/view/',
                   'https://cn.dataone.org/cn/v2/resolve/']


class DataOneImportProvider(ImportProvider):
    def __init__(self):
        super().__init__('DataONE')

    def matches(self, entity: Entity) -> bool:
        # need to deal with knb.ecoinformatics.org and other such places since, e.g.,
        # doi:10.5063/F1JM27VG points there
        url = entity.getValue()
        for base_url in ALL_LOCATIONS_2:
            if url.startswith(base_url):
                return True
        return False

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

    def register(self, parent: object, parentType: str, progress, user, dataMap: DataMap,
                 base_url: str=DataONELocations.prod_cn):
        pid = dataMap.getDataId()
        name = dataMap.getName()
        folder = self._register(parent, parentType, progress, user, pid, name, base_url)
        return ('folder', folder)

    def _register(self, parent: object, parentType: str, progress, user, pid: str, name: str,
                  base_url: str = DataONELocations.prod_cn):
        """Create a package description (Dict) suitable for dumping to JSON."""
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

        gc_folder = ModelImporter.model('folder').createFolder(
            parent, name, description='',
            parentType=parentType, creator=user, reuseExisting=True)
        gc_folder = ModelImporter.model('folder').setMetadata(
            gc_folder, {'identifier': primary_metadata[0]['identifier'],
                        'provider': 'DataONE'})

        fileModel = ModelImporter.model('file')
        itemModel = ModelImporter.model('item')
        for fileObj in data:
            try:
                fileName = fileObj['fileName']
            except KeyError:
                fileName = fileObj['identifier']

            gc_item = itemModel.createItem(
                fileName, user, gc_folder, reuseExisting=True)
            gc_item = itemModel.setMetadata(
                gc_item, {'identifier': fileObj['identifier']})

            fileModel.createLinkFile(
                url=fileObj['url'], parent=gc_item,
                name=fileName, parentType='item',
                creator=user, size=int(fileObj['size']),
                mimeType=fileObj['formatId'], reuseExisting=True)

        # Recurse and add child packages if any exist
        if children is not None and len(children) > 0:
            for child in children:
                logger.debug('Registering child package, {}'.debug(child['identifier']))
                self._register(gc_folder, 'folder', progress, user,
                                          child['identifier'],
                                          base_url)

        logger.debug('Finished registering dataset')
        return gc_folder

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
