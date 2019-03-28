from hashlib import sha256, md5
from girder.utility import hash_state, ziputil
from girder.constants import AccessType
from girder.models.folder import Folder
from ..license import WholeTaleLicense
from ..manifest import Manifest
from ...models.image import Image


class HashFileStream:
    """Generator that computes md5 and sha256 of data returned by it"""

    def __init__(self, gen):
        """
        This class is primarily meant to wrap Girder's download function,
        which returns iterators, hence self.x = x()
        """
        try:
            self.gen = gen()
        except TypeError:
            self.gen = gen
        self.state = {
            'md5': hash_state.serializeHex(md5()),
            'sha256': hash_state.serializeHex(sha256()),
        }

    def __iter__(self):
        return self

    def __next__(self):
        nxt = next(self.gen)
        for alg in self.state.keys():
            checksum = hash_state.restoreHex(self.state[alg], alg)
            checksum.update(nxt)
            self.state[alg] = hash_state.serializeHex(checksum)
        return nxt

    def __call__(self):
        """Needs to be callable, see comment in __init__"""
        return self

    @property
    def sha256(self):
        return hash_state.restoreHex(self.state['sha256'], 'sha256').hexdigest()

    @property
    def md5(self):
        return hash_state.restoreHex(self.state['md5'], 'md5').hexdigest()


class TaleExporter:

    default_top_readme = "Instructions on running the docker container"
    default_bagit = "BagIt-Version: 0.97\nTag-File-Character-Encoding: UTF-8\n"

    def __init__(self, tale, user, algs=None, expand_folders=False):
        if algs is None:
            self.algs = ["md5", "sha256"]
        self.tale = tale
        self.user = user
        self.image = Image().load(
            tale['imageId'],
            user=user,
            fields=['config', 'description', 'icon', 'iframe', 'name', 'tags'],
            level=AccessType.READ,
        )
        self.image.pop('_id')
        self.workspace = Folder().load(
            tale['workspaceId'], user=user, level=AccessType.READ
        )
        self.manifest = Manifest(tale, user, expand_folders).manifest
        self.zip_generator = ziputil.ZipGenerator(str(tale['_id']))
        self.tale_license = WholeTaleLicense().license_from_spdx(
            tale.get('licenseSPDX', WholeTaleLicense.default_spdx())
        )
        self.state = {}
        for alg in self.algs:
            self.state[alg] = []

    def stream(self):
        raise NotImplementedError

    @staticmethod
    def stream_string(string):
        return (_.encode() for _ in (string,))

    def dump_and_checksum(self, func, zip_path):
        hash_file_stream = HashFileStream(func)
        for data in self.zip_generator.addFile(hash_file_stream, zip_path):
            yield data
        for alg in self.algs:
            self.state[alg].append((zip_path, getattr(hash_file_stream, alg)))
