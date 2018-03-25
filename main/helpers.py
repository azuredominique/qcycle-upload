import ohapi
from django.conf import settings
from open_humans.models import OpenHumansMember
import logging
from project_admin.models import ProjectConfiguration
import zipfile
import bz2
import gzip
import os

logger = logging.getLogger(__name__)
OH_OAUTH2_REDIRECT_URI = '{}/complete'.format(settings.OPENHUMANS_APP_BASE_URL)
OH_BASE_URL = settings.OPENHUMANS_OH_BASE_URL


def get_create_member(data):
    '''
    use the data returned by `ohapi.api.oauth2_token_exchange`
    and return an oh_member object
    '''
    oh_id = ohapi.api.exchange_oauth2_member(
        access_token=data['access_token'])['project_member_id']
    try:
        oh_member = OpenHumansMember.objects.get(oh_id=oh_id)
        logger.debug('Member {} re-authorized.'.format(oh_id))
        oh_member.access_token = data['access_token']
        oh_member.refresh_token = data['refresh_token']
        oh_member.token_expires = OpenHumansMember.get_expiration(
            data['expires_in'])
    except OpenHumansMember.DoesNotExist:
        oh_member = OpenHumansMember.create(
            oh_id=oh_id,
            data=data)
        logger.debug('Member {} created.'.format(oh_id))
    oh_member.save()
    return oh_member


def oh_code_to_member(code):
    """
    Exchange code for token, use this to create and return OpenHumansMember.
    If a matching OpenHumansMember already exists in db, update and return it.
    """
    proj_config = ProjectConfiguration.objects.get(id=1)
    if not (proj_config.oh_client_secret and
            proj_config.oh_client_id and code):
        logger.error('OH_CLIENT_SECRET or code are unavailable')
        return None
    data = ohapi.api.oauth2_token_exchange(
        client_id=proj_config.oh_client_id,
        client_secret=proj_config.oh_client_secret,
        code=code,
        redirect_uri=OH_OAUTH2_REDIRECT_URI,
        base_url=OH_BASE_URL)
    if 'error' in data:
        logger.debug('Error in token exchange: {}'.format(data))
        return None

    if 'access_token' in data:
        return get_create_member(data)
    else:
        logger.warning('Neither token nor error info in OH response!')
        return None


VCF_FIELDS = ['CHROM', 'POS', 'ID', 'REF', 'ALT', 'QUAL', 'FILTER',
              'INFO', 'FORMAT', '23ANDME_DATA']


def vcf_header(source=None, reference=None, format_info=None):
    """
    Generate a VCF header.
    """
    header = []
    today = date.today()

    header.append('##fileformat=VCFv4.1')
    header.append('##fileDate=%s%s%s' % (str(today.year),
                                         str(today.month).zfill(2),
                                         str(today.day).zfill(2)))

    if source:
        header.append('##source=' + source)

    if reference:
        header.append('##reference=%s' % reference)

    for item in format_info:
        header.append('##FORMAT=' + item)

    header.append('#' + '\t'.join(VCF_FIELDS))

    return header


def filter_archive(zip_file):
    return [f for f in zip_file.namelist()
            if not f.startswith('__MACOSX/')]


def open_archive(input_file):
    error_message = ("Input file is expected to be either '.txt', "
                     "'.txt.gz', '.txt.bz2', or a single '.txt' file in a "
                     "'.zip' ZIP archive.")
    if input_file.name.endswith('.zip'):
        zip_file = zipfile.ZipFile(input_file)
        zip_files = filter_archive(zip_file)

        if len(zip_files) != 1:
            logger.warn(error_message)
            raise ValueError(error_message)

        return zip_file.open(zip_files[0])
    elif input_file.name.endswith('.txt.gz'):
        return gzip.open(input_file.name)
    elif input_file.name.endswith('.txt.bz2'):
        return bz2.BZ2File(input_file.name)
    elif input_file.name.endswith('.txt'):
        return open(input_file.name)

    logger.warn(error_message)
    raise ValueError(error_message)


def temp_join(tmp_directory, path):
    return os.path.join(tmp_directory, path)
