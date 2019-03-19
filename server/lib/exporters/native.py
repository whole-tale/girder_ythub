import json
from girder.constants import AccessType
from girder.models.folder import Folder
from girder.utility import ziputil
from . import default_top_readme, HashFileStream
from ..license import WholeTaleLicense
from ..manifest import Manifest


def stream(tale, user):
    zip_generator = ziputil.ZipGenerator(str(tale['_id']))

    state = {}
    # Add the license
    tale_license = WholeTaleLicense().license_from_spdx(
        tale.get('licenseSPDX', WholeTaleLicense.default_spdx())
    )
    extra_files = {
        'README.txt': default_top_readme,
        'LICENSE': tale_license['text'],
        'environment.txt': str(tale['imageId'])
    }

    def dump_and_checksum(func, zip_path):
        hash_file_stream = HashFileStream(func)
        for data in zip_generator.addFile(hash_file_stream, zip_path):
            yield data
        state[zip_path] = hash_file_stream.md5

    def stream_string(string):
        return (_.encode() for _ in (string,))

    # Add files from the workspace
    folder = Folder().load(tale['workspaceId'], user=user, level=AccessType.READ)
    for path, fobj in Folder().fileList(folder, user=user, subpath=False):
        yield from dump_and_checksum(fobj, 'workspace/' + path)

    # Compute checksums for extra files
    for path, content in extra_files.items():
        payload = stream_string(content)
        yield from dump_and_checksum(payload, path)

    # Add manifest.json
    manifest_doc = Manifest(tale, user)
    manifest = manifest_doc.manifest

    # Update manifest with hashes
    for path in state.keys():
        uri = '../' + path
        index = next(
            (i for (i, d) in enumerate(manifest['aggregates']) if d['uri'] == uri), None
        )
        if index is not None:
            manifest['aggregates'][index]['md5'] = state[path]

    # Update manifest with filesizes and mimeTypes
    for path, fobj in Folder().fileList(folder, user=user, subpath=False, data=False):
        uri = '../workspace/' + path
        index = next(
            (i for (i, d) in enumerate(manifest['aggregates']) if d['uri'] == uri), None
        )
        if index is not None:
            manifest['aggregates'][index]['mimeType'] = fobj['mimeType']
            manifest['aggregates'][index]['size'] = fobj['size']

    # Need to handle extra files coming not from girder...
    for path, content in extra_files.items():
        uri = '../' + path
        index = next(
            (i for (i, d) in enumerate(manifest['aggregates']) if d['uri'] == uri), None
        )
        if index is not None:
            manifest['aggregates'][index]['mimeType'] = 'text/plain'
            manifest['aggregates'][index]['size'] = len(content)

    for data in zip_generator.addFile(
        lambda: json.dumps(manifest, indent=4), 'metadata/manifest.json'
    ):
        yield data

    yield zip_generator.footer()
