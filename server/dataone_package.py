import hashlib
import xml.etree.cElementTree as ET

from girder import logger
from girder.models.file import File
from girder.models.item import Item
from girder.api.rest import RestException

from .utils import \
    check_pid, \
    get_file_format, \
    get_tale_description

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

    res_map = createSimpleResourceMap(resmap_pid, eml_pid, file_pids)
    # createSimpleResourceMap returns type d1_common.resource_map.ResourceMap
    return res_map.serialize()


def create_minimum_eml(tale, user, item_ids, eml_pid):
    """
    Creates a bare minimum EML record for a package.

    :param tale: The tale that is being packaged.
    :param user: The user that hit the endpoint
    :param item_ids: A lsit of the item ids of the objects that are going to be packaged
    :param eml_pid: The PID for the eml document. Assume that this is the package doi
    :type tale: wholetale.models.tale
    :type user: girder.models.user
    :type item_ids: list
    :type eml_pid: str
    :return: The EML as as string of bytes
    :rtype: bytes
    """

    """
    Check that we're able to assign a first, last, and email to the record.
    If we aren't throw an exception and let the user know. We'll also check that
    the user has an ORCID ID set.
    """

    lastName = user.get('lastName', None)
    firstName = user.get('firstName', None)
    email = user.get('email', None)

    if any((None for x in [lastName, firstName, email])):
        raise RestException('Unable to find your name or email address. Please ensure '
                            'you have authenticated with DataONE.')

    ns = ET.Element('eml:eml')
    ns.set('xmlns:eml', "eml://ecoinformatics.org/eml-2.1.1")
    ns.set('xsi:schemaLocation', "eml://ecoinformatics.org/eml-2.1.1 eml.xsd")
    ns.set('xmlns:stmml', "http://www.xml-cml.org/schema/stmml-1.1")
    ns.set('xmlns:xsi', "http://www.w3.org/2001/XMLSchema-instance")
    ns.set('scope', "system")
    ns.set('system', "knb")
    ns.set('packageId', eml_pid)

    dataset = ET.SubElement(ns, 'dataset')
    ET.SubElement(dataset, 'title').text = str(tale.get('title', ''))

    creator = ET.SubElement(dataset, 'creator')
    individual_name = ET.SubElement(creator, 'individualName')
    ET.SubElement(individual_name, 'givenName').text = firstName
    ET.SubElement(individual_name, 'surName').text = lastName

    # Only add an abstract section if the tale has a description
    description = get_tale_description(tale)
    if description is not str():
        abstract = ET.SubElement(dataset, 'abstract')
        ET.SubElement(abstract, 'para').text = description

    contact = ET.SubElement(dataset, 'contact')
    ind_name = ET.SubElement(contact, 'individualName')
    ET.SubElement(ind_name, 'givenName').text = firstName
    ET.SubElement(ind_name, 'surName').text = lastName

    # Add a <otherEntity> block for each object
    for item_id in item_ids:
        item = Item().load(item_id, user=user)
        description = item['description']

        other_entity = ET.SubElement(dataset, 'otherEntity')
        ET.SubElement(other_entity, 'entityName').text = item['name']
        ET.SubElement(other_entity, 'entityDescription').text = description if\
            bool(len(description)) else 'None'

        physical = ET.SubElement(other_entity, 'physical')
        ET.SubElement(physical, 'objectName').text = item['name']
        size_element = ET.SubElement(physical, 'size')
        size_element.text = str(item['size'])
        size_element.set('unit', 'bytes')
        format = get_file_format(item_id, user)
        data_format = ET.SubElement(physical, 'dataFormat')
        externally_defined = ET.SubElement(data_format, 'externallyDefinedFormat')
        ET.SubElement(externally_defined, 'formatName').text = format

        ET.SubElement(other_entity, 'entityType').text = 'Other'

    # call decode to get the string representation instead of as a byte str
    xml = ET.tostring(ns, encoding='UTF-8', xml_declaration=True, method='xml').decode()
    return xml


def get_file_md5(file_object, md5):
    """
    Computes the md5 of a file on the Girder filesystem.

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
        logger.warning('Error: {}'.format(e))
        return None
    finally:
        handle.close()
    return md5


def generate_system_metadata(pid, format_id, file_object, name, is_file=False):
    """
    Generates a metadata document describing the file_object.

    :param pid: The pid that the object will have
    :param format_id: The format of the object (e.g text/csv)
    :param file_object: The object that is being described
    :param name: The name of the object being described
    :param is_file: A bool set to true if file_object is a girder file
    :type pid: str
    :type format_id: str
    :type file_object: unicode or girder.models.file
    :type name: str
    :type is_file: Bool
    :return: The metadata describing file_object
    :rtype: d1_common.types.generated.dataoneTypes_v2_0.SystemMetadata
    """

    md5 = hashlib.md5()
    if is_file:
        md5 = get_file_md5(file_object, md5)
        size = file_object['size']
    else:
        # Check that the file_object is unicode, attempt to convert it if it's a str
        if not isinstance(file_object, bytes):
            if isinstance(file_object, str):
                logger.debug('file_object detected to be a string. Attempting conversion')
                file_object = file_object.encode("utf-8")
        md5.update(file_object)
        size = len(file_object)

    md5 = md5.hexdigest()
    sys_meta = populate_sys_meta(pid,
                                 format_id,
                                 size,
                                 md5,
                                 name)
    return sys_meta


def populate_sys_meta(pid, format_id, size, md5, name):
    """
    Fills out the system metadata object with the needed properties

    :param pid: The pid of the system metadata document
    :param format_id: The format of the document being described
    :param size: The size of the document that is being described
    :param md5: The md5 hash of the document being described
    :param name: The name of the file
    :type pid: str
    :type format_id: str
    :type size: int
    :type md5: str
    :type name: str
    :return: The populated system metadata document
    """

    pid = check_pid(pid)
    sys_meta = dataoneTypes.systemMetadata()
    sys_meta.identifier = pid
    sys_meta.formatId = format_id
    sys_meta.size = size
    sys_meta.rightsHolder = 'http://orcid.org/0000-0000-0000-0000'

    sys_meta.checksum = dataoneTypes.checksum(str(md5))
    sys_meta.checksum.algorithm = 'MD5'
    sys_meta.accessPolicy = generate_public_access_policy()
    sys_meta.fileName = name
    return sys_meta


def generate_public_access_policy():
    """
    Creates the access policy for the system metadata.
     Note that the permission is set to 'read'.

    :return: The access policy
    :rtype: d1_common.types.generated.dataoneTypes_v1.AccessPolicy
    """

    access_policy = dataoneTypes.accessPolicy()
    access_rule = dataoneTypes.AccessRule()
    access_rule.subject.append(d1_const.SUBJECT_PUBLIC)
    permission = dataoneTypes.Permission('read')
    access_rule.permission.append(permission)
    access_policy.append(access_rule)
    return access_policy
