from datetime import datetime, timezone
from hashlib import sha256, md5
import json
from girder.models.folder import Folder
from girder.utility import JsonEncoder
from . import TaleExporter


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


class BagTaleExporter(TaleExporter):

    def stream(self):
        extra_files = {
            'data/README.txt': self.default_top_readme,
            'data/LICENSE': self.tale_license['text'],
        }
        oxum = dict(size=0, num=0)

        # Add files from the workspace computing their checksum
        for path, file_stream in Folder().fileList(
            self.workspace, user=self.user, subpath=False
        ):
            yield from self.dump_and_checksum(file_stream, 'data/workspace/' + path)

        # Iterate again to get file sizes this time
        for path, fobj in Folder().fileList(
            self.workspace, user=self.user, subpath=False, data=False
        ):
            oxum['num'] += 1
            oxum['size'] += fobj['size']

        # Compute checksums for the extrafiles
        for path, content in extra_files.items():
            oxum['num'] += 1
            oxum['size'] += len(content)
            payload = self.stream_string(content)
            yield from self.dump_and_checksum(payload, path)

        # In Bag there's an aditional 'data' folder where everything lives
        for i in range(len(self.manifest['aggregates'])):
            uri = self.manifest['aggregates'][i]['uri']
            if uri.startswith('../'):
                self.manifest['aggregates'][i]['uri'] = uri.replace('..', '../data')
            if 'bundledAs' in self.manifest['aggregates'][i]:
                folder = self.manifest['aggregates'][i]['bundledAs']['folder']
                self.manifest['aggregates'][i]['bundledAs']['folder'] = folder.replace(
                    '..', '../data'
                )

        fetch_file = ""
        # Update manifest with hashes
        for bundle in self.manifest['aggregates']:
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

        def dump_checksums(alg):
            dump = ""
            for path, chksum in self.state[alg]:
                dump += "{} {}\n".format(chksum, path)
            return dump

        tagmanifest = dict(md5="", sha256="")
        for payload, fname in (
            (lambda: self.default_bagit, 'bagit.txt'),
            (lambda: bag_info, 'bag-info.txt'),
            (lambda: fetch_file, 'fetch.txt'),
            (lambda: dump_checksums('md5'), 'manifest-md5.txt'),
            (lambda: dump_checksums('sha256'), 'manifest-sha256.txt'),
            (
                lambda: json.dumps(
                    self.image, indent=4, cls=JsonEncoder, sort_keys=True, allow_nan=False
                ),
                'metadata/environment.json',
            ),
            (lambda: json.dumps(self.manifest, indent=4), 'metadata/manifest.json'),
        ):
            tagmanifest['md5'] += "{} {}\n".format(
                md5(payload().encode()).hexdigest(), fname
            )
            tagmanifest['sha256'] += "{} {}\n".format(
                sha256(payload().encode()).hexdigest(), fname
            )
            yield from self.zip_generator.addFile(payload, fname)

        for payload, fname in (
            (lambda: tagmanifest['md5'], 'tagmanifest-md5.txt'),
            (lambda: tagmanifest['sha256'], 'tagmanifest-sha256.txt'),
        ):
            yield from self.zip_generator.addFile(payload, fname)

        yield self.zip_generator.footer()
