from girder import logger
from girder.models.item import Item
from girder.constants import AccessType

from .dataone_register import find_initial_pid


def get_file_item(item_id, user):
    """
    Gets the file out of an item.

    :param item_id: The item that has the file inside.
    :param user: The user that is calling this
    :type: item_id: str
    :type user: girder.models.user
    :return: The file object or None
    :rtype: girder.models.file
    """

    logger.debug('Entered get_file_item')
    doc = Item().load(item_id, level=AccessType.ADMIN, user=user)

    if doc is None:
        logger.debug('Failed to load Item. Leaving get_file_item')
        return None
    child_files = Item().childFiles(doc)

    if bool(child_files):
        # We follow a rule of there only being one file per item, so return the 0th element
        logger.debug('Leaving get_file_item')
        return child_files[0]

    logger.debug('Failed to find a file. Leaving get_file_item')
    return None


def get_dataone_url(item_id, user):
    """
    Checks whether the file is linked externally to DataONE. If it is, it
    will return the url to the object

    :param item_id: The id of the item containing the file in question
    :param user: The user requesting the information
    :type item_id: str
    :type user: girder.models.user
    :return: The object's path in DataONE, None otherwise
    :rtype: str, None
    """
    logger.debug('Entered check_in_dataone')
    url = get_file_item(item_id, user).get('linkUrl')
    if url is not None:
        # if url.find('cn.dataone.org'): This will not work for dev testing.
        #  Uncomment this when it is time to implement
        #    return True
        if url.find('stage-2.test.dataone'):
            logger.debug('Leaving check_in_dataone')
            return url

    logger.debug('Leaving check_in_dataone')
    return None


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
    logger.debug('Entered check_pid')
    if not isinstance(pid, str):
        logger.debug('Warning: PID was passed that is not a str')
        logger.debug('Leaving check_pid')
        return str(pid)
    else:
        logger.debug('Leaving check_pid')
        return pid


def filter_input_items(item_ids, user):
    """
    Take a list of item ids and determine whether the file is linked to DataONE. If it is, then
    it stores its pid in the dict.

    If the file is on the filesystem, the model.File describing the file is added to the dict.

    :param item_ids: A list of items to be processed
    :param user: The user that is requesting the package creation
    :type item_ids: list
    :type user: girder.models.user
    :return: A dictionary of lists
    :rtype: dict
    """

    logger.debug('Entered filter_input_items')
    dataone_objects = list()
    # globus_objects = list()
    local_objects = list()

    for item_id in item_ids:
        url = get_dataone_url(item_id, user)
        if url is not None:
            dataone_objects.append(find_initial_pid(url))
            continue

        # url = get_globus_url(item_id, user)
        # if url is not None:
        #     globus_objects.append(url)
        #    continue

        local_objects.append(get_file_item(item_id, user))

    logger.debug('Leaving filter_input_items')
    return {'dataone': dataone_objects, 'local': local_objects}
