from .entity import Entity
from .data_map import DataMap
from .file_map import FileMap
from .import_providers import ImportProvider


class NullImportProvider(ImportProvider):
    def __init__(self):
        super().__init__('null')

    def matches(self, entity: Entity) -> bool:
        return True

    def lookup(self, entity: Entity) -> DataMap:
        raise Exception('Failed to interpret "%s" in any meaningful way' % entity.getValue())

    def listFiles(self, entity: Entity) -> FileMap:
        raise Exception('Failed to interpret "%s" in any meaningful way' % entity.getValue())
