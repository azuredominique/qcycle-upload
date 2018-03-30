from django.test import TestCase, RequestFactory
import vcr
from django.conf import settings
from django.core.management import call_command
from open_humans.models import OpenHumansMember
import os
import tempfile
import requests
import requests_mock
from main.celery import process_file


class ManagementTestCase(TestCase):
    """
    test that files are parsed correctly
    """

    def setUp(self):
        """
        Set up the app for following tests
        """
        settings.DEBUG = True
        call_command('init_proj_config')
        self.factory = RequestFactory()
        data = {"access_token": 'myaccesstoken',
                "refresh_token": 'bar',
                "expires_in": 36000}
        self.oh_member = OpenHumansMember.create(oh_id='1234',
                                                 data=data)
        self.oh_member.save()
        self.user = self.oh_member.user
        self.user.save()

    @vcr.use_cassette('main/tests/fixtures/process_file.yaml',
                      record_mode='none')
    def test_management_process_file(self):
        with requests_mock.Mocker() as m:
            m.register_uri("GET",
                           "https://www.openhumans.org/api/direct-sharing/project/exchange-member/?access_token=myaccesstoken",
                           json={'data':
                                 [{'id': 34567,
                                   'basename': '23andme_valid.txt',
                                   'created': '2018-03-30T00:09:36.563486Z',
                                   'download_url': 'https://myawslink.com/member-files/direct-sharing-1337/1234/23andme_valid.txt?Signature=nope&Expires=1522390374&AWSAccessKeyId=nope',
                                   'metadata': {'tags': ['bar'], 'description': 'foo'},
                                   'source': 'direct-sharing-1337'}]})
            call_command('process_files')
