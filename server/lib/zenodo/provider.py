import json
import re
import pathlib
from urllib.parse import urlparse, urlunparse
from urllib.request import urlopen, Request

from girder.models.folder import Folder
from girder.models.item import Item
from girder.models.setting import Setting

from ..import_providers import ImportProvider
from ..data_map import DataMap
from ..file_map import FileMap
from ..import_item import ImportItem
from ..entity import Entity
from ... import constants


class ZenodoImportProvider(ImportProvider):
    def __init__(self):
        super().__init__("Zenodo")
        # TODO: add 'data.caltech.edu'
        # however it's totally different in terms of storing data...
        self.base_targets = ["https://zenodo.org/record/"]

    def create_regex(self):
        urls = self.get_extra_hosts_setting() + self.base_targets

        locations = []
        for url in urls:
            entry = urlparse(url)
            locations.append(entry.netloc + entry.path)

        return re.compile("^http(s)?://(" + "|".join(locations) + ").*$")

    @staticmethod
    def get_extra_hosts_setting():
        return Setting().get(constants.PluginSettings.ZENODO_EXTRA_HOSTS)

    def getDatasetUID(self, doc: object, user: object) -> str:
        try:
            identifier = doc["meta"]["identifier"]  # if root of ds, it should have it
        except (KeyError, TypeError):
            if "folderId" in doc:
                path_to_root = Item().parentsToRoot(doc, user=user)
            else:
                path_to_root = Folder().parentsToRoot(doc, user=user)
            # Collection{WT Catalog} / Folder{WT Catalog} / Folder{Zenodo ds root}
            identifier = path_to_root[2]["object"]["meta"]["identifier"]
        return identifier

    def _get_record(self, raw_url):
        url = urlparse(raw_url)
        record_id = url.path.rsplit("/", maxsplit=1)[1]
        req = Request(
            urlunparse(url._replace(path="/api/records/" + record_id)),
            headers={"accept": "application/vnd.zenodo.v1+json"},
        )
        resp = urlopen(req)
        return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _get_doi_from_record(record):
        return "doi:" + record["doi"]

    @staticmethod
    def _get_title_from_record(record):
        try:
            version = record["metadata"]["version"]
        except KeyError:
            try:
                version = record["metadata"]["relations"]["version"][0]["count"]
            except (KeyError, IndexError):
                version = record["id"]
        return record["metadata"]["title"] + "_ver_{}".format(version)

    def lookup(self, entity: Entity) -> DataMap:
        record = self._get_record(entity.getValue())
        size = sum((file_obj["size"] for file_obj in record["files"]))
        return DataMap(
            entity.getValue(),
            size,
            doi=self._get_doi_from_record(record),
            name=self._get_title_from_record(record),
            repository=self.getName(),
        )

    def listFiles(self, entity: Entity) -> FileMap:
        stack = []
        top = None
        for item in self._listRecursive(entity.getUser(), entity.getValue(), None):
            if item.type == ImportItem.FOLDER:
                if len(stack) == 0:
                    fm = FileMap(item.name)
                else:
                    fm = stack[-1].addChild(item.name)
                stack.append(fm)
            elif item.type == ImportItem.END_FOLDER:
                top = stack.pop()
            elif item.type == ImportItem.FILE:
                stack[-1].addFile(item.name, item.size)
        return top

    @staticmethod
    def _files_to_hierarchy(files):
        hierarchy = {"+files+": []}

        for file_obj in files:
            temp = hierarchy
            for subdir in pathlib.Path(file_obj["key"]).parts[:-1]:
                if subdir not in temp:
                    temp[subdir] = {"+files+": []}
                temp = temp[subdir]
            temp["+files+"].append(
                {
                    "size": file_obj["size"],
                    "name": file_obj["key"].rsplit("/", maxsplit=1)[-1],
                    "url": file_obj["links"]["self"],
                    "mimeType": "application/octet-stream",
                }
            )
        return hierarchy

    def _listRecursive(
        self, user, pid: str, name: str, base_url: str = None, progress=None
    ):
        record = self._get_record(pid)

        def _recurse_hierarchy(hierarchy):
            files = hierarchy.pop("+files+")
            for obj in files:
                yield ImportItem(
                    ImportItem.FILE,
                    obj["name"],
                    size=obj["size"],
                    mimeType=obj["mimeType"],
                    url=obj["url"],
                )
            for folder in hierarchy.keys():
                yield ImportItem(ImportItem.FOLDER, name=folder)
                yield from _recurse_hierarchy(hierarchy[folder])
                yield ImportItem(ImportItem.END_FOLDER)

        meta = {k: record.get(k, "") for k in ["conceptdoi", "conceptrecid"]}
        meta["subProvider"] = urlparse(pid).netloc

        yield ImportItem(
            ImportItem.FOLDER,
            name=self._get_title_from_record(record),
            identifier=self._get_doi_from_record(record),
            meta=meta,
        )
        yield from _recurse_hierarchy(self._files_to_hierarchy(record["files"]))
        yield ImportItem(ImportItem.END_FOLDER)
