import json
from girder.constants import AccessType
from girder.models.folder import Folder
from girder.utility import ziputil
from . import default_top_readme
from ..license import WholeTaleLicense
from ..manifest import Manifest


def stream(tale, user):
    zip_generator = ziputil.ZipGenerator(str(tale['_id']))

    # Add files from the workspace
    folder = Folder().load(tale['workspaceId'], user=user, level=AccessType.READ)
    for (path, f) in Folder().fileList(folder, user=user, subpath=False):
        for data in zip_generator.addFile(f, 'workspace/' + path):
            yield data

    # Add manifest.json
    manifest_doc = Manifest(tale, user)
    for data in zip_generator.addFile(
        lambda: json.dumps(manifest_doc.manifest, indent=4), 'metadata/manifest.json'
    ):
        yield data

    # Add top level README
    for data in zip_generator.addFile(lambda: default_top_readme, 'README.txt'):
        yield data

    # Add the environment
    for data in zip_generator.addFile(lambda: str(tale['imageId']), 'environment.txt'):
        yield data

    # Add the license
    tale_license = WholeTaleLicense().license_from_spdx(
        tale.get('licenseSPDX', WholeTaleLicense.default_spdx())
    )
    tale_license = tale_license['text']
    for data in zip_generator.addFile(lambda: tale_license, 'LICENSE'):
        yield data

    yield zip_generator.footer()
