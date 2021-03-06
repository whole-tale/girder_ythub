from datetime import datetime, timezone
from hashlib import sha256, md5
import json
import os
from girder.utility import JsonEncoder
from . import TaleExporter
from gwvolman.constants import REPO2DOCKER_VERSION


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

run_tpl = r"""#!/bin/sh

# Use repo2docker to build the image from the workspace
docker run  \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "`pwd`/data/workspace:/WholeTale/workspace" \
  -v "`pwd`/metadata/environment.json:/WholeTale/workspace/.wholetale/environment.json" \
  --privileged=true \
  -e DOCKER_HOST=unix:///var/run/docker.sock \
  {repo2docker} \
  jupyter-repo2docker \
    --config=/wholetale/repo2docker_config.py \
    --target-repo-dir=/WholeTale/workspace \
    --user-id=1000 --user-name={user} \
    --no-clean --no-run --debug \
    --image-name wholetale/tale_{taleId} \
    /WholeTale/workspace

docker run --rm \
    -v "`pwd`:/bag" \
    -ti {repo2docker} bdbag --resolve-fetch all /bag

echo "========================================================================"
echo " Open your browser and go to: http://localhost:{port}/{urlPath} "
echo "========================================================================"

# Run the built image
docker run -p {port}:{port} \
  -v "`pwd`/data/data:/WholeTale/data" \
  -v "`pwd`/data/workspace:/WholeTale/workspace" \
  wholetale/tale_{taleId} {command}

"""


readme_tpl = """# Tale: "{title}" in BDBag Format

{description}

# Running locally

If you have Docker installed, you can run this Tale locally using the
following command:

```
sh ./run-local.sh
```

Access on http://localhost:{port}/{urlPath}
"""


class BagTaleExporter(TaleExporter):
    def stream(self):
        token = 'wholetale'
        container_config = self.image['config']
        rendered_command = container_config.get('command', '').format(
            base_path='', port=container_config['port'], ip='0.0.0.0', token=token
        )
        urlPath = container_config['urlPath'].format(token=token)
        run_file = run_tpl.format(
            repo2docker=container_config.get('repo2docker_version', REPO2DOCKER_VERSION),
            user=container_config['user'],
            port=container_config['port'],
            taleId=self.tale['_id'],
            command=rendered_command,
            urlPath=urlPath,
        )
        top_readme = readme_tpl.format(
            title=self.tale['title'],
            description=self.tale['description'],
            port=container_config['port'],
            urlPath=urlPath,
        )
        extra_files = {
            'data/LICENSE': self.tale_license['text'],
        }
        oxum = dict(size=0, num=0)

        # Add files from the workspace computing their checksum
        for fullpath, relpath in self.list_workspace():
            yield from self.dump_and_checksum(
                self.bytes_from_file(fullpath), 'data/workspace/' + relpath
            )
            oxum["num"] += 1
            oxum["size"] += os.path.getsize(fullpath)

        # Compute checksums for the extrafiles
        for path, content in extra_files.items():
            oxum['num'] += 1
            oxum['size'] += len(content)
            payload = self.stream_string(content)
            yield from self.dump_and_checksum(payload, path)

        # In Bag there's an additional 'data' folder where everything lives
        for i in range(len(self.manifest['aggregates'])):
            uri = self.manifest['aggregates'][i]['uri']
            # Don't touch any of the extra files
            if len([key for key in extra_files.keys() if '../' + key in uri]):
                continue
            if uri.startswith('../'):
                self.manifest['aggregates'][i]['uri'] = uri.replace('..', '../data')
            if 'bundledAs' in self.manifest['aggregates'][i]:
                folder = self.manifest['aggregates'][i]['bundledAs']['folder']
                self.manifest['aggregates'][i]['bundledAs']['folder'] = folder.replace(
                    '..', '../data'
                )
        # Update manifest with hashes
        self.append_aggergate_checksums()

        # Update manifest with filesizes and mimeTypes for workspace items
        self.append_aggregate_filesize_mimetypes('../data/workspace/')

        # Update manifest with filesizes and mimeTypes for extra items
        self.append_extras_filesize_mimetypes(extra_files)

        # Create the fetch file
        fetch_file = ""
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
            (lambda: top_readme, 'README.md'),
            (lambda: run_file, 'run-local.sh'),
            (lambda: self.default_bagit, 'bagit.txt'),
            (lambda: bag_info, 'bag-info.txt'),
            (lambda: fetch_file, 'fetch.txt'),
            (lambda: dump_checksums('md5'), 'manifest-md5.txt'),
            (lambda: dump_checksums('sha256'), 'manifest-sha256.txt'),
            (
                lambda: json.dumps(
                    self.get_environment(),
                    indent=4,
                    cls=JsonEncoder,
                    sort_keys=True,
                    allow_nan=False,
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
