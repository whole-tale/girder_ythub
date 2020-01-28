import os
import string
import unicodedata


class ImportItem:
    FILE = 0
    FOLDER = 1
    END_FOLDER = 2

    def __init__(
        self,
        type,
        name: str = None,
        identifier: str = None,
        url: str = None,
        size: int = -1,
        mimeType: str = None,
        meta=None,
    ):
        self.type = type
        if name is not None:
            self.name = self.sanitize_filename(name)
        else:
            self.name = name
        self.identifier = identifier
        self.url = url
        self.size = size
        self.mimeType = mimeType
        self.meta = meta

    @staticmethod
    def sanitize_filename(filename):
        # Adapted from
        # https://stackoverflow.com/questions/13939120/sanitizing-a-file-path-in-python

        # Sort out unicode characters
        valid_filename = (
            unicodedata.normalize(u"NFKD", filename)
            .encode("ascii", "ignore")
            .decode("ascii")
        )

        # Replace path separators with underscores
        for sep in os.path.sep, os.path.altsep:
            if sep:
                valid_filename = valid_filename.replace(sep, "_")

        # Ensure only valid characters
        valid_chars = "-_.() {0}{1}".format(string.ascii_letters, string.digits)
        valid_filename = "".join(ch for ch in valid_filename if ch in valid_chars)

        # Ensure at least one letter or number to ignore names such as '..'
        valid_chars = "{0}{1}".format(string.ascii_letters, string.digits)
        test_filename = "".join(ch for ch in filename if ch in valid_chars)

        if len(test_filename) == 0:
            # Replace empty file name or file path part with the following
            valid_filename = "(Empty Name)"
        return valid_filename
