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
    default_top_readme = """This zip file contains the code, data, and information about a Tale.

    Directory Structure:
       metadata/: Holds information about the runtime environment and Tale attributes
       workspace/: Contains the files and folders that were used in the Tale
       LICENSE: The license that the code and data falls under
       README.md: This file"""
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
        self.image["config"].update(tale.get("config", {}))  # respect config precedence
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

    def append_aggergate_checksums(self):
        """
        Takes the md5 checksums and adds them to the files in the 'aggregates' section
        :return: None
        """
        for path, chksum in self.state['md5']:
            uri = '../' + path
            index = next(
                (
                    i
                    for (i, d) in enumerate(self.manifest['aggregates'])
                    if d['uri'] == uri
                ),
                None,
            )
            if index is not None:
                self.manifest['aggregates'][index]['md5'] = chksum

    def append_aggregate_filesize_mimetypes(self, prepended_path):
        """
        Adds the file size and mimetype to the workspace files
        :param prepended_path: Any additions to the file URI
        :type prepended_path: str
        :return: None
        """
        for path, fobj in Folder().fileList(
            self.workspace, user=self.user, subpath=False, data=False
        ):
            uri = prepended_path + path
            index = next(
                (
                    i
                    for (i, d) in enumerate(self.manifest['aggregates'])
                    if d['uri'] == uri
                ),
                None,
            )
            if index is not None:
                self.manifest['aggregates'][index]['mimeType'] = (
                    fobj['mimeType'] or 'application/octet-stream'
                )
                self.manifest['aggregates'][index]['size'] = fobj['size']

    def append_extras_filesize_mimetypes(self, extra_files):
        """
        Appends the mimetype and size to the extra files in the 'aggregates 'section
        :param extra_files: Dictionary of extra file names
        :type extra_files: dict
        :return: None
        """
        for path, content in extra_files.items():
            uri = '../' + path
            index = next(
                (
                    i
                    for (i, d) in enumerate(self.manifest['aggregates'])
                    if d['uri'] == uri
                ),
                None,
            )
            if index is not None:
                self.manifest['aggregates'][index]['mimeType'] = 'text/plain'
                self.manifest['aggregates'][index]['size'] = len(content)
