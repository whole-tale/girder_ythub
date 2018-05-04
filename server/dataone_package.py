import datetime
import hashlib

from girder import logger
from girder.models.file import File
from .dataone_utils import check_pid

from d1_common.types import dataoneTypes
from d1_common import const as d1_const
from d1_common.resource_map import createSimpleResourceMap


def create_resource_map(resmap_pid, eml_pid, file_pids):
    """
    Creates a resource map for the package.

    :param resmap_pid: The pid od the resource map
    :param eml_pid: The pid of the science metadata
    :param file_pids: The pids for each file in the package
    :type resmap_pid: str
    :type eml_pid: str
    :type file_pids: list
    :return: The resource map for the package
    :rtype: bytes
    """

    print("FILE_PIDS      ", file_pids)
    logger.debug('Entered create_resource_map')
    res_map = createSimpleResourceMap(resmap_pid, eml_pid, file_pids)
    # createSimpleResourceMap returns type d1_common.resource_map.ResourceMap

    logger.debug('Leaving create_resource_map')
    return res_map.serialize()


def create_minimum_eml(tale, user):
    """
    Creates a bare minimum EML record for a package. This includes the title,
    creator, and contact.

    :param tale: The tale that is being packaged.
    :param user: The user that hit the endpoint
    :type tale: wholetale.models.tale
    :type user: girder.models.user
    :return: The EML as as string of bytes
    :rtype: bytes
    """

    logger.debug('Entered create_minimum_eml')
    top = '<?xml version="1.0" encoding="UTF-8"?>'
    namespace = '<eml:eml xmlns:eml="eml://ecoinformatics.org/eml-2.1.1" ' \
                'xmlns:stmml="http://www.xml-cml.org/schema/stmml-1.1" xmlns:' \
                'xsi="http://www.w3.org/2001/XMLSchema-instance" packageId="' \
                'doi:10.18739/A20Q25" system="https://arcticdata.io" xsi:' \
                'schemaLocation="eml://ecoinformatics.org/eml-2.1.1 eml.xsd">'

    dataset = '<dataset>\n'
    title = '<title>{0}</title>\n'.format(str(tale.get('title', '')))

    individual_name = '<individualName>\n<surName>\n{0}\n</surName>\n</individualName>'.format(
        str(user.get('lastName', '')))

    creator = '<creator>\n{0}\n</creator>\n'.format(individual_name)
    contact = '<contact>\n{0}\n</contact>\n'.format(individual_name)
    dataset_close = '</dataset>\n'
    eml_close = '</eml:eml>'

    # Append the above xml together to form the EML document
    xml = top+namespace+dataset+title+creator+contact+dataset_close+eml_close

    logger.debug('Leaving create_minimum_eml')
    return xml.encode("utf-8")


def get_file_md5(file_object, md5):
    """
    Computes the md5 of a file on the Girder Filesystem.

    :param file_object: The file object that will be hashed
    :param md5: The md5 object which will generate and hold the hash
    :type file_object: girder.models.file
    :type md5: md5
    :return: Returns an updated md5 object. Returns None if it fails
    :rtype: md5
    """

    assetstore = File().getAssetstoreAdapter(file_object)

    try:
        handle = assetstore.open(file_object)

        while True:
            buf = handle.read(8192)
            if not buf:
                break
            md5.update(buf)

    except Exception as e:
        logger.debug('Error: {}'.format(e))
        handle.close()
        return None
    handle.close()
    return md5


def generate_system_metadata(pid, format_id, file_object, is_file=False):
    """
    Generates a metadata document describing the file_object
    :param pid: The pid that the object will have
    :param format_id: The format of the object (e.g text/csv)
    :param file_object: The object that is being described
    :param is_file: A bool set to true if file_object is a girder file
    :type pid: str
    :type format_id: str
    :type file_object: unicode
    :type is_file: Bool
    :return: The metadata describing file_object
    :rtype: d1_common.types.generated.dataoneTypes_v2_0.SystemMetadata
    """

    logger.debug('Entered generate_system_metadata')
    md5 = hashlib.md5()
    if is_file:
        md5 = get_file_md5(file_object, md5)
        size = file_object['size']
    else:
        # Check that the file_object is unicode, attempt to convert it if it's a str
        if not isinstance(file_object, bytes):
            logger.debug('Warning: file_object is not unicode')
            if isinstance(file_object, str):
                logger.debug('file_object detected to be a string. Attempting conversion')
                file_object = file_object.encode("utf-8")
            else:
                raise ValueError('Supplied file_object is not unicode')
        md5.update(file_object)
        size = len(file_object)

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
    :type pid: str
    :type format_id: str
    :type size: int
    :type md5: str
    :type now: datetime
    :return: The populated system metadata document
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

    :return: The access policy
    :rtype: d1_common.types.generated.dataoneTypes_v1.AccessPolicy
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
