from girder.utility.model_importer import ModelImporter

from .entity import Entity
from .data_map import DataMap
from .file_map import FileMap
from .import_item import ImportItem


class ImportProvider:
    def __init__(self, name):
        self.name = name
        self.folderModel = ModelImporter.model('folder')
        self.itemModel = ModelImporter.model('item')
        self.fileModel = ModelImporter.model('file')

    def getName(self) -> str:
        return self.name

    def matches(self, entity: Entity) -> bool:
        raise NotImplementedError()

    def lookup(self, entity: Entity) -> DataMap:
        raise NotImplementedError()

    def listFiles(self, entity: Entity) -> FileMap:
        raise NotImplementedError()

    def register(self, parent: object, parentType: str, progress, user, dataMap: DataMap,
                 base_url: str=None):
        stack = [(parent, parentType)]
        pid = dataMap.getDataId()
        name = dataMap.getName()
        rootObj = None
        rootType = None

        for item in self._listRecursive(user, pid, name, base_url, progress=progress):
            if item.type == ImportItem.FOLDER:
                (obj, objType) = self._registerFolder(stack, item, user)
            elif item.type == ImportItem.END_FOLDER:
                stack.pop()
            elif item.type == ImportItem.FILE:
                (obj, objType) = self._registerFile(stack, item, user)
            else:
                raise Exception('Unknown import item type: %s' % item.type)
            if rootObj is None:
                rootObj = obj
                rootType = objType

        return rootType, rootObj

    def _registerFolder(self, stack, item: ImportItem, user):
        (parent, parentType) = stack[-1]
        folder = self.folderModel.createFolder(parent, item.name, description='',
                                               parentType=parentType, creator=user,
                                               reuseExisting=True)
        folder = self.folderModel.setMetadata(folder, {'identifier': item.identifier,
                                                       'provider': self.getName()})
        stack.append((folder, 'folder'))
        return (folder, 'folder')

    def _registerFile(self, stack, item: ImportItem, user):
        (parent, parentType) = stack[-1]
        gitem = self.itemModel.createItem(item.name, user, parent, reuseExisting=True)
        if item.identifier:
            gitem = self.itemModel.setMetadata(gitem, {'identifier': item.identifier})

        # girder does not allow anything else than http and https. So we need a better
        # mechanism here to communicate relevant information to WTDM
        self.fileModel.createLinkFile(item.name, url=item.url, parent=gitem, parentType='item',
                                      creator=user, size=item.size, mimeType=item.mimeType,
                                      reuseExisting=True)
        return (gitem, 'item')

    def _listRecursive(self, user, pid: str, name: str, base_url: str=None, progress=None):
        raise NotImplementedError()


class ImportProviders:
    def __init__(self):
        self.providers = []
        self.providerMap = {}

    def addProvider(self, provider: ImportProvider):
        self.providers.append(provider)
        self.providerMap[provider.getName()] = provider

    def getProvider(self, entity: Entity) -> ImportProvider:
        for provider in self.providers:
            if provider.matches(entity):
                return provider
        raise Exception('Could not find suitable provider for entity %s' % entity)

    def getFromDataMap(self, dataMap: DataMap) -> ImportProvider:
        return self.providerMap[dataMap.getRepository()]
