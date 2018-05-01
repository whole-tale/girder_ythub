import hashlib
import datetime

from girder import logger
from girder.models.model_base import ValidationException

from d1_client.mnclient_2_0 import MemberNodeClient_2_0
from d1_common.types import dataoneTypes
from d1_common import const as d1_const


def create_client(repoName, auth_token):
    """
    Creates and returns a member node client
    :param repoName:
    :param auth_token:
    :type repoName: str
    :type auth_token: dict
    :return: A client for communicating with a DataONE node
    :rtype: MemberNodeClient_2_0
    """

    return MemberNodeClient_2_0(repoName, **auth_token)


def check_pid(pid):
    """
    Check that a pid is of type str. Pids are generated as uuid4, and this
    check is done to make sure the programmer has converted it to a str before
    attempting to use it with the DataONE client.

    :param pid:
    :type pid: str, int
    :return: Returns the pid as a str, or just the pid if it was already a str
    :rtype: str
    """
    logger.debug('Entered check_pid')
    if not isinstance(pid, str):
        logger.debug('Warning: PID was passed to upload_file that is not a str')
        logger.debug('Leaving check_pid')
        return str(pid)
    else:
        logger.debug('Leaving check_pid')
        return pid


def generate_system_metadata(pid, format_id, science_object):
    """
    Generates a system metadata document.
    :param pid: The pid that the object will have
    :param format_id: The format of the object (e.g text/csv)
    :param science_object: The object that is being described
    :type pid: str
    :type format_id: str
    :type science_object:  unicode
    :return:
    """

    logger.debug('Entered generate_system_metadata')
    # Check that the science_object is unicode, attempt to convert it if it's a str
    if not isinstance(science_object, bytes):
        logger.debug('ERROR: science_object is not unicode')
        if isinstance(science_object, str):
            logger.debug('science_object detected to be a string. Attempting conversion')
            science_object = science_object.encode("utf-8")
        else:
            raise ValueError('Supplied science_object is not unicode')

    size = len(science_object)
    md5 = hashlib.md5()
    md5.update(science_object)
    md5 = md5.hexdigest()
    now = datetime.datetime.now()
    sys_meta = populate_sys_meta(pid, format_id, size, md5, now)
    logger.debug('Leaving generate_system_metadata')
    return sys_meta


def populate_sys_meta(pid, format_id, size, md5, now):
    """
    Fills out the system metadata object with the needed properties
    :param pid: The pid of the system metadata document
    :param format_id: The format of the document being described
    :param size: The size of the document that is being described
    :param md5: The md5 hash of the document being described
    :param now: The current date & time
    """

    logger.debug('Entered generate_sys_meta')
    pid = check_pid(pid)
    sys_meta = dataoneTypes.systemMetadata()
    sys_meta.identifier = pid
    sys_meta.formatId = format_id
    sys_meta.size = size
    sys_meta.rightsHolder = 'http://orcid.org/0000-0000-0000-0000'

    sys_meta.checksum = dataoneTypes.checksum(str(md5))
    sys_meta.checksum.algorithm = 'MD5'
    sys_meta.dateUploaded = now
    sys_meta.dateSysMetadataModified = now
    sys_meta.accessPolicy = generate_public_access_policy()
    logger.debug('Leaving generate_sys_meta')
    return sys_meta


def generate_public_access_policy():
    """
    Creates the access policy for the object. Note that the permission is set to 'read'.
    """

    logger.debug('Entering generate_public_access_policy')
    access_policy = dataoneTypes.accessPolicy()
    access_rule = dataoneTypes.AccessRule()
    access_rule.subject.append(d1_const.SUBJECT_PUBLIC)
    permission = dataoneTypes.Permission('read')
    access_rule.permission.append(permission)
    access_policy.append(access_rule)
    logger.debug('Leaving generate_public_access_policy')
    return access_policy


def upload_file(client, pid, object, system_metadata):
    """
    Uploads two files to a DataONE member node. The first is an object, which is just a data file.
    The second is a metadata file describing the file object.

    :param client: A client for communicating with a member node
    :param pid: The pid of the data object
    :param object: The file object that will be uploaded to the member node
    :param system_metadata: The metadata object describing the file object
    :type client: MemberNodeClient_2_0
    :type pid: str
    :type object: str
    :type system_metadata: pyxb
    """

    logger.debug('Entered upload_file')
    pid = check_pid(pid)
    try:
        client.create(pid, object, system_metadata)
        logger.debug('Uploaded file')

    except Exception as e:
        raise ValidationException('Error uploading file to DataONE {0}'.format(str(e)))
