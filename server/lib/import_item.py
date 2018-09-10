class ImportItem:
    FILE = 0
    FOLDER = 1
    END_FOLDER = 2

    def __init__(self, type, name: str=None, identifier: str=None, url: str=None, size: int=-1,
                 mimeType: str=None, meta=None):
        self.type = type
        self.name = name
        self.identifier = identifier
        self.url = url
        self.size = size
        self.mimeType = mimeType
        self.meta = meta