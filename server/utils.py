import six.moves.urllib as urllib

from girder.utility.model_importer import ModelImporter


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


class DataONELocations:
    """
    An enumeration that describes the different DataONE
    endpoints.
    """
    # Production coordinating node
    prod_cn = 'https://cn.dataone.org/cn/v2'
    # Development member node
    dev_mn = 'https://dev.nceas.ucsb.edu/knb/d1/mn/v2'
    # Development coordinating node
    dev_cn = 'https://cn-stage-2.test.dataone.org/cn/v2'