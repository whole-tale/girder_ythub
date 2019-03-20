from datetime import datetime, timezone
from hashlib import sha256, md5
import json
from girder.constants import AccessType
from girder.models.folder import Folder
from girder.utility import ziputil
from . import default_top_readme, default_bagit, HashFileStream
from ..license import WholeTaleLicense
from ..manifest import Manifest


bag_profile = (
    "https://raw.githubusercontent.com/fair-research/bdbag/"
    "master/profiles/bdbag-ro-profile.json"
)
bag_info_tpl = """Bag-Software-Agent: WholeTale version: 0.7
BagIt-Profile-Identifier: {bag_profile}
Bagging-Date: {date}
Bagging-Time: {time}
Payload-Oxum: {oxum}
"""


def stream(tale, user):
    zip_generator = ziputil.ZipGenerator(str(tale['_id']))
    state = dict(sha256="", md5="")
    # Get License
    tale_license = WholeTaleLicense().license_from_spdx(
        tale.get('licenseSPDX', WholeTaleLicense.default_spdx())
    )
    extra_files = {
        'data/README.txt': default_top_readme,
        'data/LICENSE': tale_license['text'],
    }

    def dump_and_checksum(func, zip_path):
        hash_file_stream = HashFileStream(func)
        for data in zip_generator.addFile(hash_file_stream, zip_path):
            yield data
        state['sha256'] += "{}  {}\n".format(hash_file_stream.sha256, zip_path)
        state['md5'] += "{}  {}\n".format(hash_file_stream.md5, zip_path)

    def stream_string(string):
        return (_.encode() for _ in (string,))

    oxum = dict(size=0, num=0)

    # Add files from the workspace computing their checksum
    folder = Folder().load(tale['workspaceId'], user=user, level=AccessType.READ)
    for path, file_stream in Folder().fileList(folder, user=user, subpath=False):
        yield from dump_and_checksum(file_stream, 'data/workspace/' + path)

    # Iterate again to get file sizes this time
    for path, fobj in Folder().fileList(folder, user=user, subpath=False, data=False):
        oxum['num'] += 1
        oxum['size'] += fobj['size']

    # Compute checksums for the extrafiles
    for path, content in extra_files.items():
        oxum['num'] += 1
        oxum['size'] += len(content)
        payload = stream_string(content)
        yield from dump_and_checksum(payload, path)

    manifest_doc = Manifest(tale, user)
    manifest = manifest_doc.manifest
    # In Bag there's an aditional 'data' folder where everything lives
    for i in range(len(manifest['aggregates'])):
        uri = manifest['aggregates'][i]['uri']
        if uri.startswith('../'):
            manifest['aggregates'][i]['uri'] = uri.replace('..', '../data')
        if 'bundledAs' in manifest['aggregates'][i]:
            folder = manifest['aggregates'][i]['bundledAs']['folder']
            manifest['aggregates'][i]['bundledAs']['folder'] = folder.replace(
                '..', '../data'
            )

    fetch_file = ""
    # Update manifest with hashes
    for bundle in manifest['aggregates']:
        if 'bundledAs' not in bundle:
            continue
        folder = bundle['bundledAs']['folder']
        fetch_file += "{uri} {size} {folder}".format(
            uri=bundle['uri'], size=bundle['size'], folder=folder.replace('../', '')
        )  # fetch.txt is located in the root level, need to adjust paths
        fetch_file += bundle['bundledAs'].get('filename', '')
        fetch_file += '\n'

    now = datetime.now(timezone.utc)
    bag_info = bag_info_tpl.format(
        bag_profile=bag_profile,
        date=now.strftime('%Y-%m-%d'),
        time=now.strftime('%H:%M:%S %Z'),
        oxum="{size}.{num}".format(**oxum),
    )

    tagmanifest = dict(md5="", sha256="")
    for payload, fname in (
        (lambda: default_bagit, 'bagit.txt'),
        (lambda: bag_info, 'bag-info.txt'),
        (lambda: fetch_file, 'fetch.txt'),
        (lambda: state['md5'], 'manifest-md5.txt'),
        (lambda: state['sha256'], 'manifest-sha256.txt'),
        (lambda: str(tale['imageId']), 'metadata/environment.txt'),
        (lambda: json.dumps(manifest_doc.manifest, indent=4), 'metadata/manifest.json'),
    ):
        tagmanifest['md5'] += "{} {}\n".format(
            md5(payload().encode()).hexdigest(), fname
        )
        tagmanifest['sha256'] += "{} {}\n".format(
            sha256(payload().encode()).hexdigest(), fname
        )
        yield from zip_generator.addFile(payload, fname)

    for payload, fname in (
        (lambda: tagmanifest['md5'], 'tagmanifest-md5.txt'),
        (lambda: tagmanifest['sha256'], 'tagmanifest-sha256.txt'),
    ):
        yield from zip_generator.addFile(payload, fname)

    yield zip_generator.footer()
