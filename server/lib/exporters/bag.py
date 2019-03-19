import json
from hashlib import sha256, md5
from girder.constants import AccessType
from girder.models.folder import Folder
from girder.utility import ziputil, hash_state
from . import default_top_readme, default_bagit
from ..license import WholeTaleLicense
from ..manifest import Manifest


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


def stream(tale, user):
    zip_generator = ziputil.ZipGenerator(str(tale['_id']))
    state = dict(sha256="", md5="")

    def dump_and_checksum(func, zip_path):
        hash_file_stream = HashFileStream(func)
        for data in zip_generator.addFile(hash_file_stream, zip_path):
            yield data
        state['sha256'] += "{}  {}\n".format(hash_file_stream.sha256, zip_path)
        state['md5'] += "{}  {}\n".format(hash_file_stream.md5, zip_path)

    def stream_string(string):
        return (_.encode() for _ in (string,))

    # Add files from the workspace computing their checksum
    folder = Folder().load(tale['workspaceId'], user=user, level=AccessType.READ)
    for (path, f) in Folder().fileList(folder, user=user, subpath=False):
        yield from dump_and_checksum(f, 'data/workspace/' + path)

    # Get License
    tale_license = WholeTaleLicense().license_from_spdx(
        tale.get('licenseSPDX', WholeTaleLicense.default_spdx())
    )
    tale_license_text = tale_license['text']
    # Compute checksums for the following
    for payload, fname in (
        (stream_string(default_top_readme), 'data/README.txt'),
        (stream_string(tale_license_text), 'data/LICENSE'),
    ):
        yield from dump_and_checksum(payload, fname)

    manifest_doc = Manifest(tale, user)
    for payload, fname in (
        (lambda: json.dumps(manifest_doc.manifest, indent=4), 'metadata/manifest.json'),
        (lambda: str(tale['imageId']), 'metadata/environment.txt'),
        (lambda: state['sha256'], 'manifest-sha256.txt'),
        (lambda: state['md5'], 'manifest-md5.txt'),
        (lambda: default_bagit, 'bagit.txt')
    ):
        yield from zip_generator.addFile(payload, fname)

    yield zip_generator.footer()
