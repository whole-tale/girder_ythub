from .entity import Entity
from .data_map import DataMap
from .file_map import FileMap


class ImportProvider:
    def __init__(self, name):
        self.name = name

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
