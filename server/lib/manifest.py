import os

from ..constants import CATALOG_NAME, WORKSPACE_NAME
from .license import WholeTaleLicense
from . import IMPORT_PROVIDERS

from girder import logger
from girder.models.folder import Folder
from girder.utility.model_importer import ModelImporter
from girder.utility import path as path_util
from girder.exceptions import ValidationException
from girder.constants import AccessType


class Manifest:
    """
    Class that represents the manifest file.
    Methods that add information to the manifest file have the form
    add_<someProperty>
    while methods that create chunks of the manifest have the form
    create<someProperty>
    """

    def __init__(self, tale, user, item_ids=None):
        """
        Initialize the manifest document with base variables
        :param tale: The Tale whose data is being serialized
        :param user: The user requesting the manifest document
        :param item_ids: An optional list of items to include in the manifest
        """
        self.tale = tale
        self.user = user

        self.manifest = dict()
        self.item_ids = item_ids
        # Create a set that represents any external data packages
        self.datasets = set()

        self.folderModel = ModelImporter.model('folder')
        self.itemModel = ModelImporter.model('item')
        self.userModel = ModelImporter.model('user')

        self.manifest.update(self.create_context())
        self.manifest.update(self.create_basic_attributes())
        self.add_tale_creator()

        if self.item_ids:
            self.add_item_records()
        else:
            self.add_tale_records()
        # Add any external datasets to the manifest
        self.add_dataset_records()
        self.add_system_files()

    publishers = {
        "DataONE":
            {
                "@id": "https://www.dataone.org/",
                "@type": "Organization",
                "legalName": "DataONE",
                "Description": "A federated data network allowing access to science data"
            },
        "Globus":
            {
                "@id": "https://www.materialsdatafacility.org/",
                "@type": "Organization",
                "legalName": "Materials Data Facility",
                "Description": "A simple way to publish, discover, and access materials datasets"
            }
    }

    def create_basic_attributes(self):
        """
        Returns a portion of basic attributes in the manifest
        :return: Basic information about the Tale
        """

        return {
            "@id": 'https://data.wholetale.org/api/v1/tale/' + str(self.tale['_id']),
            "createdOn": str(self.tale['created']),
            "schema:name": self.tale['title'],
            "schema:description": self.tale.get('description', str()),
            "schema:category": self.tale['category'],
            "schema:identifier": str(self.tale['_id']),
            "schema:version": self.tale['format'],
            "schema:image": self.tale['illustration'],
            "aggregates": list(),
            "Datasets": list()
        }

    def add_tale_creator(self):
        """
        Adds basic information about the Tale author
        """

        tale_user = self.userModel.load(self.tale['creatorId'],
                                        user=self.user,
                                        force=True)
        self.manifest['createdBy'] = {
            "@id": self.tale['authors'],
            "@type": "schema:Person",
            "schema:givenName": tale_user.get('firstName', ''),
            "schema:familyName": tale_user.get('lastName', ''),
            "schema:email": tale_user.get('email', '')
        }

    def create_context(self):
        """
        Creates the manifest namespace. When a new vocabulary is used, it shoud
        get added here.
        :return: A structure defining the used vocabularies
        """
        return {
            "@context": [
                "https://w3id.org/bundle/context",
                {"schema": "http://schema.org/"},
                {"Datasets": {"@type": "@id"}}
            ]
        }

    def create_dataset_record(self, folder_id):
        """
        Creates a record that describes a Dataset
        :param folder_id: Folder that represents a dataset
        :return: Dictionary that describes a dataset
        """
        try:
            folder = self.folderModel.load(folder_id,
                                           user=self.user,
                                           exc=True,
                                           level=AccessType.READ)
            provider = folder['meta']['provider']
            if provider in {'HTTP', 'HTTPS'}:
                return None
            identifier = folder['meta']['identifier']
            return {
                "@id": identifier,
                "@type": "Dataset",
                "name": folder['name'],
                "identifier": identifier,
                "publisher": self.publishers[provider]}

        except (KeyError, TypeError, ValidationException) as e:
            msg = 'While creating a manifest for Tale "{}" '.format(str(self.tale['_id']))
            msg += 'encountered a following error:\n'
            msg += str(e)
            logger.warning(msg)
            pass

    def create_aggregation_record(self, uri, bundle=None, parent_dataset_identifier=None):
        """
        Creates an aggregation record. Externally defined aggregations should include
        a bundle and a parent_dataset if it belongs to one
        :param uri: The item's URI in the manifest, typically it's path
        :param bundle: An optional bundle that's needed for externally defined data
        :param parent_dataset_identifier: The ID of an optional parent dataset
        :return: Dictionary representing an aggregated file
        """
        aggregation = dict()
        aggregation['uri'] = uri
        if bundle:
            aggregation['bundledAs'] = bundle
        if parent_dataset_identifier:
            aggregation['schema:isPartOf'] = parent_dataset_identifier
        return aggregation

    def add_item_records(self):
        """
        Creates records for a set of item ids. This is desired when the mainfest is being generated
        for a subset of files in a Tale. Note that these records get added to the internal manifest
        object.
        """
        for item_id in self.item_ids:
            item = self.itemModel.load(item_id,
                                       user=self.user,
                                       level=AccessType.READ)
            if item:
                item_path = path_util.getResourcePath('item', item, user=self.user)
                # Recreate the path
                data_catalog_root = '/collection/' + CATALOG_NAME+'/'+CATALOG_NAME+'/'
                workspaces_root = '/collection/' + WORKSPACE_NAME+'/'+WORKSPACE_NAME
                # Check if the item belongs to workspace or external data
                if item_path.startswith(workspaces_root):
                    item_path = item_path.replace(workspaces_root, '')
                    full_path = '../workspace' + clean_workspace_path(self.tale['_id'],
                                                                      item_path)
                    self.manifest['aggregates'].append({'uri': full_path})
                    continue
                elif item_path.startswith(data_catalog_root):
                    item_path = item_path.replace(data_catalog_root, '')
                    bundle = self.create_bundle('../data/' + item_path,
                                                clean_workspace_path(self.tale['_id'],
                                                                     item['name']))

                    # Get the linkURL from the file object
                    item_files = self.itemModel.fileList(item,
                                                         user=self.user,
                                                         data=False)
                    for file_item in item_files:
                        agg_record = self.create_aggregation_record(
                            file_item[1]['linkUrl'],
                            bundle,
                            get_folder_identifier(item['folderId'],
                                                  self.user))
                        self.manifest['aggregates'].append(agg_record)
                    self.datasets.add(item['folderId'])

            folder = self.folderModel.load(item_id,
                                           user=self.user,
                                           level=AccessType.READ)
            if folder:
                parent = self.folderModel.parentsToRoot(folder, user=self.user)
                # Check if the folder is in the workspace
                if parent[0].get('object').get('name') == WORKSPACE_NAME:
                    folder_items = self.folderModel.fileList(folder, user=self.user)
                    for folder_item in folder_items:
                        self.manifest['aggregates'].append({'uri':
                                                            '../workspace/' + folder_item[0]})

    def add_tale_records(self):
        """
        Creates and adds file records to the internal manifest object for an entire Tale.
        """

        # Handle the files in the workspace
        folder = self.folderModel.load(self.tale['workspaceId'],
                                       user=self.user,
                                       level=AccessType.READ)
        if folder:
            workspace_folder_files = self.folderModel.fileList(folder,
                                                               user=self.user,
                                                               data=False)
            for workspace_file in workspace_folder_files:
                self.manifest['aggregates'].append(
                    {'uri': '../workspace/' + clean_workspace_path(self.tale['_id'],
                                                                   workspace_file[0])})

        """
        Handle objects that are in the dataSet, ie files that point to external sources.
        Some of these sources may be datasets from publishers. We need to save information
        about the source so that they can added to the Datasets section.
        """
        external_objects, dataset_top_identifiers = self._parse_dataSet()

        # Add records of all top-level dataset identifiers that were used in the Tale:
        # "Datasets"
        for identifier in dataset_top_identifiers:
            # Assuming Folder model implicitly ignores "datasets" that are
            # single HTTP files which is intended behavior
            for folder in Folder().findWithPermissions(
                    {'meta.identifier': identifier}, limit=1, user=self.user
            ):
                self.datasets.add(folder['_id'])

        # Add records for the remote files that exist under a folder: "aggregates"
        for obj in external_objects:
            # Grab identifier of a parent folder
            parent_dataset_identifier = obj.get('dataset_identifier')
            if obj['provider'] in {'HTTP', 'HTTPS'}:
                # In case of http(s) prevent the creation of schema:isPartOf entry,
                # by setting parent ds identifier to None.
                parent_dataset_identifier = None
            bundle = self.create_bundle('../data/', obj['name'])
            record = self.create_aggregation_record(
                obj['linkUrl'], bundle, parent_dataset_identifier)
            self.manifest['aggregates'].append(record)

    def _parse_dataSet(self):
        """
        Get the basic info about the contents of `dataSet`

        Returns:
            external_objects: A list of objects that represent externally defined data
            dataset_top_identifiers: A set of DOIs for top-level packages that contain
                objects from external_objects

        """
        dataset_top_identifiers = set()
        external_objects = []
        for obj in self.tale['dataSet']:
            try:
                if obj['_modelType'] == 'folder':
                    model = self.folderModel
                elif obj['_modelType'] == 'item':
                    model = self.itemModel

                doc = model.load(obj['itemId'], user=self.user, level=AccessType.READ, exc=True)
                provider_name = doc['meta']['provider']
                if provider_name.startswith('HTTP'):
                    provider_name = 'HTTP'  # TODO: handle HTTPS to make it unnecessary
                provider = IMPORT_PROVIDERS.providerMap[provider_name]
                top_identifier = provider.getDatasetUID(doc, self.user)
                dataset_top_identifiers.add(top_identifier)

                if obj['_modelType'] == 'item':
                    fileObj = model.childFiles(doc)[0]
                    external_objects.append(
                        {
                            "dataset_identifier": top_identifier,
                            "provider": provider_name,
                            "name": fileObj['name'],
                            "linkUrl": fileObj['linkUrl']
                        }
                    )
                # elif obj['_modelType'] == 'folder':
                #  Find path to root?
            except (ValidationException, KeyError) as e:
                msg = 'While creating a manifest for Tale "{}" '.format(str(self.tale['_id']))
                msg += 'encountered a following error:\n'
                msg += str(e)
                logger.warning(msg)
                pass

        return external_objects, dataset_top_identifiers

    def add_dataset_records(self):
        """
        Adds dataset records to the manifest document
        :return: None
        """
        for folder_id in self.datasets:
            dataset_record = self.create_dataset_record(folder_id)
            if dataset_record:
                self.manifest['Datasets'].append(dataset_record)

    def create_bundle(self, folder, filename):
        """
        Creates a bundle for an externally referenced file
        :param folder: The name of the folder that the file is in
        :param filename:  The name of the file
        :return: A dictionary record of the bundle
        """

        # Add a trailing slash to the path if there isn't one (RO spec)
        os.path.join(folder, '')
        return {
            'folder': folder,
            'filename': filename
        }

    def add_system_files(self):
        """
        Add records for files that we inject (README, LICENSE, etc)
        """

        self.manifest['aggregates'].append({'uri': '../LICENSE',
                                            'schema:license':
                                                self.tale.get('licenseSPDX',
                                                              WholeTaleLicense.default_spdx())})

        self.manifest['aggregates'].append({'uri': '../README.txt',
                                            '@type': 'schema:HowTo'})

        self.manifest['aggregates'].append({'uri': '../environment.txt'})


def clean_workspace_path(tale_id, path):
    """
    Removes the Tale ID from a path
    :param tale_id: The Tale's ID
    :param path: The file path
    :return: A cleaned path
    """
    return path.replace(str(tale_id) + '/', '')


def get_folder_identifier(folder_id, user):
    """
    Gets the 'identifier' field out of a folder. If it isn't present in the
    folder, it will navigate to the folder above until it reaches the collection
    :param folder_id: The ID of the folder
    :param user: The user that is creating the manifest
    :return: The identifier of a dataset
    """
    try:
        folder = ModelImporter.model('folder').load(folder_id,
                                                    user=user,
                                                    level=AccessType.READ,
                                                    exc=True)

        meta = folder.get('meta')
        if meta:
            if meta['provider'] in {'HTTP', 'HTTPS'}:
                return None
            identifier = meta.get('identifier')
            if identifier:
                return identifier

        get_folder_identifier(folder['parentID'], user)

    except (ValidationException, KeyError):
        pass
