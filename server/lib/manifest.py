import os

from girder.utility.model_importer import ModelImporter


class Manifest:
    """
    Class that represents the manifest file.
    Methods that add information to the manifest file have the form
    add_<someProperty>
    while methods that create chunks of the manifest have the form
    create<someProperty>
    """

    def __init__(self, tale_license, item_ids=None):
        """
        Initialize the manifest document with base variables
        :param license:
        :param item_ids:
        """
        self.manifest = dict()
        self.item_ids = item_ids
        # Holds the SPDX of the license
        self.license = tale_license
        # Create a set that represents any external data packages
        self.datasets = set()

        self.folderModel = ModelImporter.model('folder')
        self.itemModel = ModelImporter.model('item')
        self.userModel = ModelImporter.model('user')

    def generate_manifest(self, user, tale):
        self.manifest.update(self.create_context())
        self.manifest.update(self.create_basic_attributes(tale))
        self.add_tale_creator(tale, user)
        self.manifest['aggregates'] = []

        if self.item_ids:
            self.add_item_records(user, tale)
        else:
            self.add_tale_records(tale, user)
        # Add any external datasets to the manifest
        self.add_dataset_records(user)
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

    def create_basic_attributes(self, tale):
        """
        Returns a portion of basic attributes in the manifest
        :param tale: A Tale that is being described
        :return: Basic information about the Tale
        """

        return {
            "@id": 'https://data.wholetale.org/api/v1/tale/' + str(tale['_id']),
            "createdOn": str(tale['created']),
            "schema:name": tale['title'],
            "schema:description": tale.get('description', str()),
            "schema:category": tale['category'],
            "schema:identifier": str(tale['_id']),
            "schema:version": tale['format'],
            "schema:image": tale['illustration'],
            "aggregates": list(),
            "Datasets": list()
        }

    def add_tale_creator(self, tale, user):
        """
        Adds basic information about the Tale author
        :param tale: The Tale being described
        :param user: The user whose information is being used
        """

        tale_user = self.userModel.load(tale['creatorId'], user=user)
        self.manifest['createdBy'] = {
            "@id": tale['authors'],
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
                {"schema": "http://schema.org/"}
            ]
        }

    def create_dataset_record(self, user, folder_id):
        """
        Creates a record that describes a Dataset
        :param user: The user
        :param folder_id: Folder that represents a dataset
        :return: Dictionary that describes a dataset
        """
        folder = self.folderModel.load(folder_id,
                                       user=user,
                                       force=True)
        if folder:
            meta = folder.get('meta')
            if meta:
                provider = meta.get('provider')
                if provider:
                    return {
                        "@id": meta.get('identifier'),
                        "@type": "Dataset",
                        "name": folder['name'],
                        "identifier": meta.get('identifier'),
                        "publisher": self.publishers[provider]}

    def create_aggregation_record(self, uri, bundle=None, parent_dataset=None):
        """
        Creates an aggregation record. Externally defined aggregations should include
        a bundle and a parent_dataset if it belongs to one
        :param uri:
        :param bundle:
        :param parent_dataset:
        :return: Dictionary representing an aggregated file
        """
        aggregation = dict()
        aggregation['uri'] = uri
        if bundle:
            aggregation['bundledAs'] = bundle
        if parent_dataset:
            aggregation['schema:isPartOf'] = parent_dataset
        return aggregation

    def add_item_records(self, user, tale):
        """
        Creates records for a set of item ids. This is desired when the mainfest is being generated
        for a subset of files in a Tale. Note that these records get added to the internal manifest
        object.
        :param user: The user that is creating the manifest
        :param tale: The tale whose information is being used
        """
        for item_id in self.item_ids:
            item = self.itemModel.load(item_id,
                                       user=user,
                                       force=True)
            if item:
                root = self.itemModel.parentsToRoot(item, user=user)

                # Recreate the path
                item_path = str()
                for path in root:
                    item_path += path['object']['name'] + '/'
                # Check if the item belongs to workspace or external data
                if 'WholeTale Workspaces/WholeTale Workspaces' in item_path:
                    item_path = item_path.replace('WholeTale Workspaces/WholeTale Workspaces', '')
                    full_path = '../workspace' + clean_workspace_path(tale['_id'],
                                                                      item_path + item['name'])
                    self.manifest['aggregates'].append({'uri': full_path})
                    continue
                elif 'WholeTale Catalog/WholeTale Catalog/' in item_path:
                    item_path = item_path.replace('WholeTale Catalog/WholeTale Catalog/', '')
                    bundle = self.create_bundle('../data/' + item_path,
                                                clean_workspace_path(tale['_id'], item['name']))

                    # Get the linkURL from the file object
                    item_files = self.itemModel.fileList(item,
                                                         user=user,
                                                         data=False)
                    for file_item in item_files:
                        agg_record = self.create_aggregation_record(
                            file_item[1]['linkUrl'],
                            bundle,
                            get_folder_identifier(item['folderId'],
                                                  user))
                        self.manifest['aggregates'].append(agg_record)
                    self.datasets.add(item['folderId'])

            folder = self.folderModel.load(item_id,
                                           user=user,
                                           force=True)
            if folder:
                parent = self.folderModel.parentsToRoot(folder, user=user)
                # Check if the folder is in the workspace
                if parent[0].get('object').get('name') == 'WholeTale Workspaces':
                    folder_items = self.folderModel.fileList(folder, user=user)
                    for folder_item in folder_items:
                        self.manifest['aggregates'].append({'uri':
                                                            '../workspace/' + folder_item[0]})

    def add_tale_records(self, tale, user):
        """
        Creates and adds file records to the internal manifest object for an entire Tale.
        :param tale: The Tale being described
        :param user: The user requesting the manifest
        """

        # Handle the files in the workspace
        folder = self.folderModel.load(tale['workspaceId'],
                                       user=user,
                                       force=True)
        if folder:
            workspace_folder_files = self.folderModel.fileList(folder,
                                                               user=user,
                                                               data=False)
            for workspace_file in workspace_folder_files:
                self.manifest['aggregates'].append(
                    {'uri': '../workspace/' + clean_workspace_path(tale['_id'],
                                                                   workspace_file[0])})

        folder_files = list()

        """
        Handle objects that are in the dataSet, ie files that point to external sources.
        Some of these sources may be datasets from publishers. We need to save information
        about the source so that they can added to the Datasets section.
        """
        folder_files = self.add_tale_datasets(tale, user, folder_files)

        # Add records for the remote files that exist under a folder
        for folder_record in folder_files:
            if folder_record['file_iterator'] is None:
                continue
            for file_record in folder_record['file_iterator']:
                # Check if the file points to an external resource
                if 'linkUrl' in file_record[1]:
                    bundle = self.create_bundle('../data/' + get_dataset_file_path(file_record),
                                                file_record[1]['name'])
                    record = self.create_aggregation_record(file_record[1]['linkUrl'],
                                                            bundle,
                                                            folder_record.get('dataset_identifier'))
                    self.manifest['aggregates'].append(record)

    def add_tale_datasets(self, tale, user, folder_files):
        """
        Adds information about the contents of `dataSet` to the manifest
        """
        for obj in tale['dataSet']:
            if obj['_modelType'] == 'folder':
                folder = self.folderModel.load(obj['itemId'],
                                               user=user,
                                               force=True)
                if folder:
                    # Check if it's a dataset by checking for meta.identifier
                    folder_meta = folder.get('meta')
                    if folder_meta:
                        dataset_identifier = folder_meta.get('identifier')
                        if dataset_identifier:
                            self.datasets.add(obj['itemId'])
                            folder_files.append(
                                {"dataset_identifier": dataset_identifier,
                                 "provider": folder_meta.get('provider'),
                                 "file_iterator": get_folder_files(folder,
                                                                   user)
                                 })

                    else:
                        folder_files.append({"file_iterator": get_folder_files(folder,
                                                                               user)})
            elif obj['_modelType'] == 'item':
                """
                If there is a file that was added to a tale that came from a dataset, but outside
                the dataset folder, we need to get metadata about the parent folder and the file.

                """
                root_item = self.itemModel.load(obj['itemId'],
                                                user=user,
                                                force=True)
                if root_item:
                    # Should always be true since the item is in dataSet
                    if root_item.get('meta'):
                        item_folder = self.folderModel.load(root_item['folderId'],
                                                            user=user,
                                                            force=True)
                        folder_meta = item_folder.get('meta')
                        if folder_meta:
                            self.datasets.add(root_item['folderId'])
                            folder_files.append({"dataset_identifier":
                                                folder_meta.get('identifier'),
                                                 "provider":
                                                     folder_meta.get('provider'),
                                                 "file_iterator":
                                                     self.itemModel.fileList(root_item,
                                                                             user=user,
                                                                             data=False)
                                                 })
        return folder_files

    def add_dataset_records(self, user):
        """
        Adds dataset records to the manifest document
        :param user: The user requesting the manifest
        :return: None
        """
        for folder_id in self.datasets:
            self.manifest['Datasets'].append(self.create_dataset_record(user, folder_id))

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
                                            'schema:license': self.license})

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
    folder = ModelImporter.model('folder').load(folder_id,
                                                user=user,
                                                force=True)
    if folder:
        meta = folder.get('meta')
        if meta:
            identifier = meta.get('identifier')
            if identifier:
                return identifier

        get_folder_identifier(folder['parentID'], user)


def get_folder_files(folder, user):
    return ModelImporter.model('folder').fileList(folder,
                                                  user=user,
                                                  data=False)


def get_dataset_file_path(file_info):
    """
    Given a full path, remove the filename
    :param file_info:
    :return: The full path without the filename
    """
    res = file_info[0].replace('/' + file_info[1]['name'], '')
    if res != file_info[0]:
        return res
    return ''
