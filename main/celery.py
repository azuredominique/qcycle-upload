from django.conf import settings
import os
from celery import Celery
import tempfile
import json
from ohapi import api
import requests

import bz2
import logging
import re
import shutil

from io import StringIO
from datetime import datetime

import arrow
from .celery_helper import vcf_header, temp_join, open_archive

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oh_data_uploader.settings')

VCF_FIELDS = ['CHROM', 'POS', 'ID', 'REF', 'ALT', 'QUAL', 'FILTER',
              'INFO', 'FORMAT', '23ANDME_DATA']

OH_BASE_URL = settings.OPENHUMANS_OH_BASE_URL
OH_API_BASE = OH_BASE_URL + '/api/direct-sharing'
OH_DIRECT_UPLOAD = OH_API_BASE + '/project/files/upload/direct/'
OH_DIRECT_UPLOAD_COMPLETE = OH_API_BASE + '/project/files/upload/complete/'

REF_23ANDME_FILE = os.path.join(os.path.dirname(__file__),
                                'references/reference_b37.txt')

# Was used to generate reference genotypes in the previous file.
REFERENCE_GENOME_URL = ('http://hgdownload-test.cse.ucsc.edu/' +
                        'goldenPath/hg19/bigZips/hg19.2bit')

logger = logging.getLogger(__name__)

app = Celery('proj')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.update(CELERY_BROKER_URL=os.environ['REDIS_URL'],
                CELERY_RESULT_BACKEND=os.environ['REDIS_URL'])

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
# app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


def read_reference(ref_file):
    reference = dict()

    with open(ref_file) as f:
        for line in f:
            data = line.rstrip().split('\t')

            if data[0] not in reference:
                reference[data[0]] = dict()

            reference[data[0]][data[1]] = data[2]
    return reference


def vcf_from_raw_23andme(raw_23andme):
    output = StringIO()

    reference = read_reference(REF_23ANDME_FILE)

    header = vcf_header(
        source='open_humans_data_importer.twenty_three_and_me',
        reference=REFERENCE_GENOME_URL,
        format_info=['<ID=GT,Number=1,Type=String,Description="Genotype">'])

    for line in header:
        output.write(line + '\n')

    for line in raw_23andme:
        # Skip header
        if line.startswith('#'):
            continue

        data = line.rstrip().split('\t')

        # Skip uncalled and genotyping without explicit base calls
        if not re.match(r'^[ACGT]{1,2}$', data[3]):
            continue
        vcf_data = {x: '.' for x in VCF_FIELDS}

        # Chromosome, position, dbSNP ID, reference. Skip if we don't have ref.
        try:
            vcf_data['REF'] = reference[data[1]][data[2]]
        except KeyError:
            continue

        if data[1] == 'MT':
            vcf_data['CHROM'] = 'M'
        else:
            vcf_data['CHROM'] = data[1]

        vcf_data['POS'] = data[2]

        if data[0].startswith('rs'):
            vcf_data['ID'] = data[0]

        # Figure out the alternate alleles.
        alt_alleles = []

        for alle in data[3]:
            if alle != vcf_data['REF'] and alle not in alt_alleles:
                alt_alleles.append(alle)

        if alt_alleles:
            vcf_data['ALT'] = ','.join(alt_alleles)
        else:
            vcf_data['ALT'] = '.'
            vcf_data['INFO'] = 'END=' + vcf_data['POS']

        # Get allele-indexed genotype.
        vcf_data['FORMAT'] = 'GT'
        all_alleles = [vcf_data['REF']] + alt_alleles
        genotype_indexed = '/'.join([str(all_alleles.index(x))
                                     for x in data[3]])
        vcf_data['23ANDME_DATA'] = genotype_indexed
        output_line = '\t'.join([vcf_data[x] for x in VCF_FIELDS])
        output.write(output_line + '\n')

    return output


def normalize_23andme_datetime(re_datetime_string, dateline):
    datetime_string = re.search(re_datetime_string,
                                dateline).groups()[0]

    re_norm_day = r'(?<=[a-z])  ([1-9])(?= [0-9][0-9]:[0-9][0-9])'
    datetime_norm = re.sub(re_norm_day, r' 0\1', datetime_string)
    datetime_23andme = datetime.strptime(datetime_norm,
                                         '%a %b %d %H:%M:%S %Y')
    return datetime_23andme


def clean_raw_23andme(closed_input_file):
    input_file = open_archive(closed_input_file)

    output = StringIO()

    dateline = input_file.readline()

    re_datetime_string = (r'([A-Z][a-z]{2} [A-Z][a-z]{2} [ 1-9][0-9] '
                          r'[0-9][0-9]:[0-9][0-9]:[0-9][0-9] 2[0-9]{3})')

    if re.search(re_datetime_string, dateline):
        datetime_23andme = normalize_23andme_datetime(re_datetime_string,
                                                      dateline)
        output.write('# This data file generated by 23andMe at: {}\r\n'
                     .format(datetime_23andme.strftime(
                         '%a %b %d %H:%M:%S %Y')))

    cwd = os.path.dirname(__file__)

    header_v1 = open(os.path.join(cwd, 'references/header-v1.txt'), 'r').read()
    header_v2 = open(os.path.join(cwd, 'references/header-v2.txt'), 'r').read()
    header_v3_p1 = open(os.path.join(cwd,
                                     'references/header-v3-p1.txt'),
                        'r').read()
    header_v3_p2 = open(os.path.join(cwd,
                                     'references/header-v3-p2.txt'),
                        'r').read()

    header_lines = ''

    next_line = input_file.readline()

    while next_line.startswith('#'):
        header_lines += next_line.rstrip() + "\n"

        next_line = input_file.readline()
    if (header_lines.splitlines() == header_v1.splitlines() or
            header_lines.splitlines() == header_v2.splitlines()):
        output.write(header_lines)
    elif (header_lines.splitlines()[:13] == header_v3_p1.splitlines() and
          header_lines.splitlines()[-5:] == header_v3_p2.splitlines()):
        output.write(header_v3_p1)
        output.write('# [URL REDACTED]\n')
        output.write(header_v3_p2)
    else:
        logger.warn('23andMe header did not conform to expected format.')

    bad_format = False

    while next_line:
        regex = re.compile(r"""(rs|i)[0-9]+
            \t[1-9XYM][0-9T]?
            \t[0-9]+
            \t[ACGT\-ID][ACGT\-ID]?
            """, re.VERBOSE)
        if re.match(regex, next_line):
            output.write(next_line)
        else:
            # Only report this type of format issue once.
            if not bad_format:
                bad_format = True
                logger.warn('23andMe body did not conform to expected format.')
                logger.warn('Bad format: "%s"', next_line)

        try:
            next_line = input_file.readline()
        except StopIteration:
            next_line = None

    if bad_format:
        logger.warn('23andMe body did not conform to expected format.')

    return output


def upload_new_file(closed_file,
                    access_token,
                    project_member_id,
                    metadata):
    with open(closed_file, 'r+b') as upload_file:
        upload_url = '{}?access_token={}'.format(
            OH_DIRECT_UPLOAD, access_token)
        req1 = requests.post(upload_url,
                             data={'project_member_id': project_member_id,
                                   'filename': upload_file.name,
                                   'metadata': json.dumps(metadata)})
        if req1.status_code != 201:
            raise Exception('Bad response when starting file upload.')
        # Upload to S3 target.
        req2 = requests.put(url=req1.json()['url'], data=upload_file)
        if req2.status_code != 200:
            raise Exception('Bad response when uploading file.')

        # Report completed upload to Open Humans.
        complete_url = ('{}?access_token={}'.format(
            OH_DIRECT_UPLOAD_COMPLETE, access_token))
        req3 = requests.post(complete_url,
                             data={'project_member_id': project_member_id,
                                   'file_id': req1.json()['id']})
        if req3.status_code != 200:
            raise Exception('Bad response when completing file upload.')


def process_file(dfile, access_token, member, metadata):
    try:
        infile_suffix = dfile['basename'].split(".")[-1]
        tf_in = tempfile.NamedTemporaryFile(suffix="."+infile_suffix)
        tf_in.write(requests.get(dfile['download_url']).content)
        tf_in.flush()
        tmp_directory = tempfile.mkdtemp()
        filename_base = '23andMe-genotyping'

        raw_23andme = clean_raw_23andme(tf_in)
        raw_23andme.seek(0)
        vcf_23andme = vcf_from_raw_23andme(raw_23andme)

        # Save raw 23andMe genotyping to temp file.
        raw_filename = filename_base + '.txt'
        raw_filename = temp_join(tmp_directory, raw_filename)
        metadata = {
                    'description':
                    '23andMe full genotyping data, original format',
                    'tags': ['23andMe', 'genotyping'],
                    'creation_date': arrow.get().format(),
            }
        with open(raw_filename, 'w') as raw_file:
            raw_23andme.seek(0)
            shutil.copyfileobj(raw_23andme, raw_file)
            raw_file.flush()

        upload_new_file(raw_filename,
                        access_token,
                        str(member['project_member_id']),
                        metadata)

        # Save VCF 23andMe genotyping to temp file.
        vcf_filename = filename_base + '.vcf.bz2'
        vcf_filename = temp_join(tmp_directory, vcf_filename)

        metadata = {
            'description': '23andMe full genotyping data, VCF format',
            'tags': ['23andMe', 'genotyping', 'vcf'],
            'creation_date': arrow.get().format()
        }
        with bz2.BZ2File(vcf_filename, 'w') as vcf_file:
            vcf_23andme.seek(0)
            for i in vcf_23andme:
                vcf_file.write(i.encode())

        upload_new_file(vcf_filename,
                        access_token,
                        str(member['project_member_id']),
                        metadata)
    except:
        api.message("23andMe integration: A broken file was deleted",
                    "While processing your 23andMe file "
                    "we noticed that your file does not conform "
                    "to the expected specifications and it was "
                    "thus deleted. Please make sure you upload "
                    "the right file:\nWe expect the file to be a "
                    "single txt file (either unzipped, bz2 zipped or gzipped) "
                    "or a .zip file that contains a single txt file (this is "
                    " what you can download from 23andMe right away) Please "
                    "do not alter the original txt file, as unexpected "
                    "additions can invalidate the file.",
                    access_token, base_url=OH_BASE_URL)
        raise

    finally:
        api.delete_file(access_token,
                        str(member['project_member_id']),
                        file_id=str(dfile['id']),
                        base_url=OH_BASE_URL)


@app.task(bind=True)
def clean_uploaded_file(self, access_token, file_id):
    member = api.exchange_oauth2_member(access_token, base_url=OH_BASE_URL)
    for dfile in member['data']:
        if dfile['id'] == file_id:
            process_file(dfile, access_token, member, dfile['metadata'])
    pass
