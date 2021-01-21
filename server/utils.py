import datetime
import six.moves.urllib as urllib

from girder.utility.model_importer import ModelImporter
from girder.models.notification import Notification


NOTIFICATION_EXP_HOURS = 1


def getOrCreateRootFolder(name, description=""):
    collection = ModelImporter.model('collection').createCollection(
        name, public=True, reuseExisting=True)
    folder = ModelImporter.model('folder').createFolder(
        collection, name, parentType='collection', public=True,
        reuseExisting=True, description=description)
    return folder


def check_pid(pid):
    """
    Check that a pid is of type str. Pids are generated as uuid4, and this
    check is done to make sure the programmer has converted it to a str before
    attempting to use it with the DataONE client.

    :param pid: The pid that is being checked
    :type pid: str, int
    :return: Returns the pid as a str, or just the pid if it was already a str
    :rtype: str
    """

    if not isinstance(pid, str):
        return str(pid)
    else:
        return pid


def esc(value):
    """
    Escape a string so it can be used in a Solr query string
    :param value: The string that will be escaped
    :type value: str
    :return: The escaped string
    :rtype: str
    """
    return urllib.parse.quote_plus(value)


def init_progress(resource, user, title, message, total):

    data = {
        'title': title,
        'total': total,
        'current': 0,
        'state': 'active',
        'message': message,
        'estimateTime': False,
        'resource': resource,
        'resourceName': 'WT custom resource'
    }

    expires = datetime.datetime.utcnow() + datetime.timedelta(hours=NOTIFICATION_EXP_HOURS)

    return Notification().createNotification(
        type="wt_progress", data=data, user=user, expires=expires)


def deep_get(dikt, path):
    """Get a value located in `path` from a nested dictionary.

    Use a string separated by periods as the path to access
    values in a nested dictionary:

    deep_get(data, "data.files.0") == data["data"]["files"][0]

    Taken from jupyter/repo2docker
    """
    value = dikt
    for component in path.split("."):
        if component.isdigit():
            value = value[int(component)]
        else:
            value = value[component]
    return value
