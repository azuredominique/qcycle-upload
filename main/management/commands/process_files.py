from django.core.management.base import BaseCommand
from open_humans.models import OpenHumansMember
from main.celery import clean_uploaded_file
from ohapi import api


class Command(BaseCommand):
    help = 'Requeue all unprocessed files for Celery'

    def check_file_raw_valid(self, file_object):
        if file_object['basename'] != '23andMe-genotyping.txt':
            return False
        if file_object['metadata']['description'] != "23andMe full genotyping data, original format":
            return False
        if file_object['metadata']['tags'] != ['23andMe', 'genotyping']:
            return False
        return True

    def check_file_vcf_valid(self, file_object):
        if file_object['basename'] != '23andMe-genotyping.vcf.bz2':
            return False
        if file_object['metadata']['description'] != "23andMe full genotyping data, VCF format":
            return False
        if file_object['metadata']['tags'] != ['23andMe', 'genotyping', 'vcf']:
            return False
        return True

    def check_file_valid(self, file_object):
        if not self.check_file_raw_valid(file_object) and not self.check_file_vcf_valid(file_object):
            return False
        return True

    def handle(self, *args, **options):
        open_humans_members = OpenHumansMember.objects.all()
        for ohmember in open_humans_members:
            ohmember_data = api.exchange_oauth2_member(
                                    ohmember.get_access_token())
            files = ohmember_data['data']
            for f in files:
                if not self.check_file_valid(f):
                    clean_uploaded_file.delay(ohmember.access_token,
                                              f['id'])
