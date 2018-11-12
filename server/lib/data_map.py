from typing import Dict, List


dataMapDoc = {
    'type': 'object',
    'description': ('A container with a basic information about '
                    'a set of external data resources.'),
    'properties': {
        'dataId': {
            'type': 'string',
            'description': 'External dataset identificator, such as URL.'
        },
        'repository': {
            'type': 'string',
            'description': 'Name of a data repository holding the dataset.'
        },
        'doi': {
            'type': 'string',
            'description': 'Digital Object Identifier'
        },
        'name': {
            'type': 'string',
            'description': ('A user-friendly name. Defaults to the name '
                            'provided by an external repository.')
        },
        'size': {
            'type': 'integer',
            'description': 'Size of the dataset in bytes.'
        }
    },
    'required': ['dataId', 'repository', 'doi', 'name', 'size'],
    'example': {
        'dataId': 'urn:uuid:42969280-e11c-41a9-92dc-33964bf785c8',
        'doi': '10.5063/F1Z899CZ',
        'name': ('Data from a dynamically downscaled projection of past and '
                 'future microclimates covering North America from 1980-1999 '
                 'and 2080-2099'),
        'repository': 'DataONE',
        'size': 178679
    },
}


class DataMap:
    def __init__(self, dataId: str, size: int, doi: str = None, name: str = None,
                 repository: str = None):
        self.dataId = dataId
        self.size = size
        self.repository = repository
        self.doi = doi
        self.name = name

    def getName(self) -> str:
        return self.name

    def getDOI(self) -> str:
        return self.doi

    def getDataId(self) -> str:
        return self.dataId

    def getRepository(self) -> str:
        return self.repository

    def setRepository(self, repository: str):
        self.repository = repository

    def getSize(self) -> int:
        return self.size

    def setSize(self, size: int):
        self.size = size

    def toDict(self) -> Dict:
        return {'dataId': self.dataId, 'size': self.size, 'repository': self.repository,
                'doi': self.doi, 'name': self.name}

    @staticmethod
    def fromDict(d: Dict):
        return DataMap(d['dataId'], d['size'], repository=d['repository'], doi=d['doi'],
                       name=d['name'])

    @staticmethod
    def fromList(d: List[Dict]):
        return [DataMap.fromDict(x) for x in d]
