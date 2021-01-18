import json
import os
import pathlib

from girder.models.file import File
from girder.models.folder import Folder

from .license import WholeTaleLicense
from ..models.image import Image


class ManifestParser:
    @staticmethod
    def get_dataset_from_manifest(manifest):
        """Creates a 'dataSet' using manifest's aggregates section."""
        dataSet = []
        for obj in manifest.get("aggregates", []):
            try:
                bundle = obj["bundledAs"]
            except KeyError:
                continue

            folder_path = bundle["folder"].replace("../data/", "")
            if "filename" in bundle:
                file_obj = File().findOne({"linkUrl": obj["uri"]}, fields=["itemId"])
                itemId = file_obj["itemId"]
                path = os.path.join(folder_path, bundle["filename"])
                model_type = "item"
            else:
                folder = Folder().findOne({"meta.identifier": obj["uri"]}, fields=[])
                if not folder:
                    fname = pathlib.Path(obj["bundledAs"]["folder"]).parts[-1]
                    # TODO: There should be a better way to do it...
                    folder = Folder().findOne({"name": fname, "size": obj["size"]}, fields=[])
                itemId = folder["_id"]
                path = folder_path
                model_type = "folder"
            dataSet.append(
                dict(mountPath=path, _modelType=model_type, itemId=str(itemId))
            )
        return dataSet

    @staticmethod
    def get_tale_fields_from_manifest(manifest):
        licenseSPDX = next(
            (
                _["schema:license"]
                for _ in manifest["aggregates"]
                if "schema:license" in _
            ),
            WholeTaleLicense.default_spdx(),
        )

        authors = [
            {
                "firstName": author["schema:givenName"],
                "lastName": author["schema:familyName"],
                "orcid": author["@id"],
            }
            for author in manifest["schema:author"]
        ]

        related_ids = [
            {
                "identifier": rel_id["DataCite:relatedIdentifier"]["@id"],
                "relation": rel_id["DataCite:relatedIdentifier"][
                    "DataCite:relationType"
                ].split(":")[-1],
            }
            for rel_id in manifest.get("DataCite:relatedIdentifiers", [])
        ]
        related_ids = [
            json.loads(rel_id)
            for rel_id in {json.dumps(_, sort_keys=True) for _ in related_ids}
        ]

        return {
            "title": manifest["schema:name"],
            "description": manifest["schema:description"],
            "illustration": manifest["schema:image"],
            "authors": authors,
            "category": manifest["schema:category"],
            "licenseSPDX": licenseSPDX,
            "relatedIdentifiers": related_ids,
        }

    @staticmethod
    def get_tale_fields_from_environment(environment):
        image = Image().findOne({"name": environment["name"]})
        icon = image.get(
            "icon",
            (
                "https://raw.githubusercontent.com/"
                "whole-tale/dashboard/master/public/"
                "images/whole_tale_logo.png"
            ),
        )
        return {
            "imageId": image["_id"],
            "icon": icon,
            "config": environment.get("taleConfig", {}),
        }
