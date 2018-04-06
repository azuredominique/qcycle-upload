from django.core.management.base import BaseCommand
from open_humans.models import OpenHumansMember
from main.celery import clean_uploaded_file
from ohapi import api
from project_admin.models import ProjectConfiguration


class Command(BaseCommand):
    help = 'Requeue all unprocessed files for Celery'

    def get_metadata_list(self, files):
        metadata_files = []
        for f in files:
            if f['basename'].endswith('.vcf.metadata.json'):
                metadata_files.append(f['basename'])
        return metadata_files

    def iterate_member_files(self, ohmember):
        client_info = ProjectConfiguration.objects.get(id=1).client_info
        ohmember_data = api.exchange_oauth2_member(
                                ohmember.get_access_token(**client_info))
        files = ohmember_data['data']
        metadata_files = self.get_metadata_list(files)
        for f in files:
            fname = f['basename']
            if fname.endswith('.gz'):
                fname = fname.replace('.gz', '')
            elif fname.endswith('bz2'):
                fname = fname.replace('.bz2', '')
            if fname + '.vcf.metadata.json' not in metadata_files:
                clean_uploaded_file.delay(ohmember.access_token,
                                          f['id'])

    def handle(self, *args, **options):
        open_humans_members = OpenHumansMember.objects.all()
        for ohmember in open_humans_members:
            self.iterate_member_files(ohmember)
