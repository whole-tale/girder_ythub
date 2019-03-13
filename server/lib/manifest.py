import os

from ..constants import CATALOG_NAME, WORKSPACE_NAME
from .license import WholeTaleLicense

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
            if provider == 'HTTP':
                return None
            identifier = folder['meta']['identifier']
            return {
                "@id": identifier,
                "@type": "Dataset",
                "name": folder['name'],
                "identifier": identifier,
                "publisher": self.publishers[provider]}

        except (KeyError, TypeError, ValidationException):
            pass

    def create_aggregation_record(self, uri, bundle=None, parent_dataset=None):
        """
        Creates an aggregation record. Externally defined aggregations should include
        a bundle and a parent_dataset if it belongs to one
        :param uri: The item's URI in the manifest, typically it's path
        :param bundle: An optional bundle that's needed for externally defined data
        :param parent_dataset: The ID of an optional parent dataset
        :return: Dictionary representing an aggregated file
        """
        aggregation = dict()
        aggregation['uri'] = uri
        if bundle:
            aggregation['bundledAs'] = bundle
        if parent_dataset:
            aggregation['schema:isPartOf'] = parent_dataset
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

        external_folders_files = list()

        """
        Handle objects that are in the dataSet, ie files that point to external sources.
        Some of these sources may be datasets from publishers. We need to save information
        about the source so that they can added to the Datasets section.
        """
        external_folders_files = self.add_tale_datasets(external_folders_files)

        # Add records for the remote files that exist under a folder
        for folder_record in external_folders_files:
            if folder_record['file_iterator'] is None:
                continue
            for file_record in folder_record['file_iterator']:
                # Check if the file points to an external resource
                if 'linkUrl' in file_record[1]:
                    bundle = self.create_bundle('../data/' + os.path.dirname(file_record[0]),
                                                file_record[1]['name'])
                    record = self.create_aggregation_record(file_record[1]['linkUrl'],
                                                            bundle,
                                                            folder_record.get('dataset_identifier'))
                    self.manifest['aggregates'].append(record)

    def add_tale_datasets(self, folder_files):
        """
        Adds information about the contents of `dataSet` to the manifest

        :param folder_files: A list of objects that represent externally defined data
        """
        for obj in self.tale['dataSet']:
            if obj['_modelType'] == 'folder':
                self.datasets.add(obj['itemId'])
            elif obj['_modelType'] == 'item':
                """
                If there is a file that was added to a tale that came from a dataset, but outside
                a folder under the dataset folder, we need to get metadata about the parent folder
                and the file.
                """
                try:
                    root_item = self.itemModel.load(obj['itemId'],
                                                    user=self.user,
                                                    level=AccessType.READ,
                                                    exc=True)
                    item_folder = self.folderModel.load(root_item['folderId'],
                                                        user=self.user,
                                                        level=AccessType.READ,
                                                        exc=True)
                    # Check if the item was added from a dataset folder, or if it was
                    # registered directly into the Catalog root
                    if item_folder['name'].startswith(CATALOG_NAME):
                        # Use the item's metadata

                        folder_files.append({"dataset_identifier":
                                            root_item['meta']['identifier'],
                                             "provider":
                                                 root_item['meta']['provider'],
                                             "file_iterator":
                                                 self.itemModel.fileList(root_item,
                                                                         user=self.user,
                                                                         data=False)})

                    else:
                        self.datasets.add(root_item['folderId'])
                        folder_files.append({"dataset_identifier":
                                            item_folder['meta']['identifier'],
                                             "provider":
                                                 item_folder['meta']['provider'],
                                             "file_iterator":
                                             self.itemModel.fileList(root_item,
                                                                     user=self.user,
                                                                     data=False)
                                             })
                except (ValidationException, KeyError):
                    pass
        return folder_files

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
            if meta['provider'] == 'HTTP':
                return None
            identifier = meta.get('identifier')
            if identifier:
                return identifier

        get_folder_identifier(folder['parentID'], user)

    except ValidationException:
        pass
