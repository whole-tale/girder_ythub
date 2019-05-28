import six.moves.urllib as urllib

from girder.utility.model_importer import ModelImporter
from girder.models.notification import Notification


def getOrCreateRootFolder(name, description=str()):
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


def init_progress(resource, user, title, message, total, expires=-1):

    data = {
       'title': title,
       'total': total,
       'current': 0,
       'state': 'active',
       'message': message,
       'estimateTime': False,
       'resource': resource,
       'resourceName': 'Custom resource'
    }

    return Notification().createNotification(
        type="progress", data=data, user=user, expires=expires)
