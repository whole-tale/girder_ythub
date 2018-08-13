import re
import jwt
import six.moves.urllib as urllib

from girder.utility.model_importer import ModelImporter
from girder import logger
from girder.models.item import Item
from girder.models.folder import Folder
from girder.constants import \
    AccessType
from girder.api.rest import RestException

from .constants import DataONELocations


def getOrCreateRootFolder(name, description=str()):
    collection = ModelImporter.model('collection').createCollection(
        name, public=True, reuseExisting=True)
    folder = ModelImporter.model('folder').createFolder(
        collection, name, parentType='collection', public=True,
        reuseExisting=True, description=description)
    return folder


def get_tale_artifacts(tale, user):
    """
    Gets meta files that describe the tale. This includes config files
    and the docker file. child_items holds the files that are in the tale
    folder-and needs to be sorted through to locate the config files.
    DEVNOTE: This currently jsut returns all of the files in the
    tale folder. This will be modified when we start saving the dockerfile.

    :param tale: The tale whose contents are to be retrieved
    :param user: The user accessing the filder
    :type tale: girder.models.Tale
    :type user: girder.models.User
    :return: A list of items that are in the folder
    :rtype list(girder.models.Item)
    """

    folder = Folder().load(
        id=tale['folderId'],
        user=user,
        level=AccessType.READ,
        exc=True)
    child_items = Folder().childItems(folder=folder)
    return child_items


def get_file_item(item_id, user):
    """
    Gets the file out of an item.

    :param item_id: The item that has the file inside
    :param user: The user that is accessing the file
    :type: item_id: str
    :type user: girder.models.User
    :return: The file object or None
    :rtype: girder.models.file
    """

    doc = Item().load(item_id, level=AccessType.READ, user=user)

    if doc is None:
        logger.warning('Failed to load item {}. Leaving get_file_item'.format(str(item_id)))
        return None
    child_files = Item().childFiles(doc)

    if bool(child_files.count()):
        # Return the first item
        return child_files.next()

    logger.warning('Failed to find a file for item {}. Leaving get_file_item'.format(str(item_id)))
    return None


def get_file_format(item_id, user):
    """
    Gets the format for a file from an item id

    :param item_id: The item that has the file inside.
    :param user: The user that is requesting the file format
    :type: item_id: str
    :type user: girder.models.user
    :return: The file's extension
    :rtype: str
    """

    file = get_file_item(item_id, user)
    if file is not None:
        return file.get('mimeType', '')


def get_tale_description(tale):
    """
    If a tale description is empty, it holds the value, 'null'. To avoid passing it
    to the UI, check if it is null, and return an empty string

    :param tale: The tale whose description is requested
    :type tale:  wholetale.models.tale
    :return: The tale description or str()
    :rtype: str
    """
    desc = tale['description']
    if desc is None:
        return str()
    return desc


def get_dataone_url(item_id, user):
    """
    Checks whether the file is linked externally to DataONE. If it is, it
    will return the url that the file links to.
    DEVNOTE: We may have to modify this to check for member nodes that don't
    have dataone in the url.

    :param item_id: The id of the item containing the file in question
    :param user: The user requesting the url
    :type item_id: str
    :type user: girder.models.user
    :return: The object's path in DataONE, None otherwise
    :rtype: str, None
    """

    file = get_file_item(item_id, user)
    if file is None:
        file_error = 'Failed to find the file with ID {}'.format(item_id)
        logger.warning(file_error)
        raise RestException(file_error)
    url = file.get('linkUrl')
    if url is not None:
        if is_dataone_url(url):
            return url


def is_dataone_url(url):
    """
    Checks if a url has dataone in it
    :param url: The url in question
    :return: True if it does, False otherwise
    """

    res = url.find('dataone.org')
    if res is not -1:
        return True
    else:
        return False


def is_dev_url(url):
    """
    Determines whether the object at the URL is on the NCEAS
    Development network
    :param url: URL to the object
    :type url: str
    :return: True of False, depending on whether it's on the dev network
    :rtype: bool
    """
    parsed_url = urllib.parse.urlparse(url).netloc
    parsed_dev_mn = urllib.parse.urlparse(DataONELocations.dev_cn).netloc

    if parsed_url == parsed_dev_mn:
        return True
    return False


def is_in_network(url, network):
    """
    Checks to see if the url shares the same netlocation as network
    :param url: The URL to a data object
    :param network: The url of the member node being checke
    :return: True or False
    """
    parsed_url = urllib.parse.urlparse(url).netloc
    parsed_network = urllib.parse.urlparse(network).netloc
    base_dev_mn = urllib.parse.urlparse(DataONELocations.dev_mn).netloc
    base_dev_cn = urllib.parse.urlparse(DataONELocations.dev_cn).netloc

    if parsed_network == base_dev_mn:
        # Then we're in NCEAS Development
        # The resolve address is through the membernode in this case
        if parsed_url == base_dev_cn:
            # Then the object is in network
            return True
        else:
            # Then the object is outside network
            return False

    else:
        # Otherwise we're on DataONE

        base_dev_cn = urllib.parse.urlparse(DataONELocations.prod_cn).netloc

        if parsed_url == base_dev_cn:
            # Then the object is in network
            return True
        else:
            # Then the object is outside network
            return False


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


def get_remote_url(item_id, user):
    """
    Checks if a file has a link url and returns the url if it does. This is less
     restrictive than thecget_dataone_url in that we aren't restricting the link
      to a particular domain.

    :param item_id:
    :param user:
    :return: The url that points to the object
    :rtype: str or None
    """

    file = get_file_item(item_id, user)
    if file is None:
        file_error = 'Failed to find the file with ID {}'.format(item_id)
        logger.warning(file_error)
        raise RestException(file_error)
    url = file.get('linkUrl')
    if url is not None:
        return url


def get_tale_files(tale, user):
    """
    Gets the tale artifacts and creates a list of files.
    :param tale: The tale whose artifacts are being extracted
    :param user: The user that is requesting the artifacts
    :type tale: wholetale.models.Tale
    :type user: girder.models.User
    :return: A list of the files
    :rtype list
    """
    artifact_items = get_tale_artifacts(tale, user)
    files = list()
    for item in artifact_items:
        files.append(get_file_item(item['_id'], user))
    return files


def get_dataone_package_url(repository, pid):
    """
    Given a repository url and a pid, construct a url that should
     be the package's landing page.

    :param repository: The repository that the package is on
    :param pid: The package pid
    :return: The package landing page
    """
    if repository in DataONELocations.prod_cn:
        return str('https://search.dataone.org/#view/'+pid)
    elif repository in DataONELocations.dev_mn:
        return str('https://dev.nceas.ucsb.edu/#view/'+pid)


def extract_user_id(jwt_token):
    """
    Takes a JWT and extracts the 'userId` field. This is used
    as the package's owner and contact.
    :param jwt: The decoded JWT
    :type jwt: str
    :return: The ORCID ID
    :rtype: str, None if failure
    """
    jwt_token = jwt.decode(jwt_token, verify=False)
    user_id = jwt_token.get('userId', None)
    if user_id is not None:
        if is_orcid_id(user_id):
            return make_url_https(user_id)
    return user_id


def is_orcid_id(id):
    """
    Checks whether a string is a link to an ORCID account
    :param id: The string that may contain the ORCID account
    :type id: str
    :return: True/False if it is or isn't
    :rtype: bool
    """
    return bool(id.find('orcid.org'))


def esc(value):
    """
    Escape a string so it can be used in a Solr query string
    :param value: The string that will be escaped
    :type value: str
    :return: The escaped string
    :rtype: str
    """
    return urllib.parse.quote_plus(value)


def strip_html_tags(string):
    """
    Removes HTML tags from a string
    :param string: The string with HTML
    :type string: str
    :return: The string without HTML
    :rtype: str
    """
    return re.sub('<[^<]+?>', '', string)


def get_directory(user_id):
    """
    Returns the directory that should be used in the EML

    :param user_id: The user ID
    :type user_id: str
    :return: The directory name
    :rtype: str
    """
    if is_orcid_id(user_id):
        return "https://orcid.org"
    return "https://cilogon.org"


def make_url_https(url):
    """
    Given an http url, return it as https

    :param url: The http url
    :type url: str
    :return: The url as https
    :rtype: str
    """
    parsed = urllib.parse.urlparse(url)
    return parsed._replace(scheme="https").geturl()
