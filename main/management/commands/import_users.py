from django.core.management.base import BaseCommand
from open_humans.models import OpenHumansMember
from project_admin.models import ProjectConfiguration


class Command(BaseCommand):
    help = 'Import existing users from legacy project'

    def add_arguments(self, parser):
        parser.add_argument('--infile', type=str,
                            help='CSV with project_member_id & refresh_token')
        parser.add_argument('--delimiter', type=str,
                            help='CSV delimiter')

    def handle(self, *args, **options):
        client_info = ProjectConfiguration.objects.get(id=1).client_info
        for line in open(options['infile']):
            line = line.strip().split(options['delimiter'])
            oh_id, refresh_token = line[0], line[1]
            if len(OpenHumansMember.objects.filter(
                     oh_id=oh_id)) == 0:
                data = {}
                data["access_token"] = "mock"
                data["refresh_token"] = refresh_token
                data["expires_in"] = -3600
                oh_member = OpenHumansMember.create(oh_id, data)
                oh_member._refresh_tokens(**client_info)
