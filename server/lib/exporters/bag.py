import json
from girder.constants import AccessType
from girder.models.folder import Folder
from girder.utility import ziputil
from . import default_top_readme, default_bagit, HashFileStream
from ..license import WholeTaleLicense
from ..manifest import Manifest


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
    manifest = manifest_doc.manifest
    fetch_file = ""
    # Update manifest with hashes
    for bundle in manifest['aggregates']:
        if 'bundledAs' not in bundle:
            continue
        folder = bundle['bundledAs']['folder']
        fetch_file += "{uri} {size} {folder}".format(
            uri=bundle['uri'], size=bundle['size'], folder=folder.replace('..', 'data'))
        fetch_file += bundle['bundledAs'].get('filename', '')
        fetch_file += '\n'

    for payload, fname in (
        (lambda: json.dumps(manifest_doc.manifest, indent=4), 'metadata/manifest.json'),
        (lambda: str(tale['imageId']), 'metadata/environment.txt'),
        (lambda: state['sha256'], 'manifest-sha256.txt'),
        (lambda: state['md5'], 'manifest-md5.txt'),
        (lambda: fetch_file, 'fetch.txt'),
        (lambda: default_bagit, 'bagit.txt'),
    ):
        yield from zip_generator.addFile(payload, fname)

    yield zip_generator.footer()
