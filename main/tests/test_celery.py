from django.test import TestCase, RequestFactory
import vcr
from django.conf import settings
from django.core.management import call_command
from open_humans.models import OpenHumansMember
from main.celery import process_file


class ParsingTestCase(TestCase):
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
        data = {"access_token": 'foo',
                "refresh_token": 'bar',
                "expires_in": 36000}
        self.oh_member = OpenHumansMember.create(oh_id='12345678',
                                                 data=data)
        self.oh_member.save()
        self.user = self.oh_member.user
        self.user.set_password('foobar')
        self.user.save()


    @vcr.use_cassette('main/tests/fixtures/process_file.yaml',
                      record_mode='none')
    def test_process_file(self):
        """
        test process_file celery task
        """

        member = {"project_member_id": "1234"}
        dfile = {'id': 34567,
                 'basename': 'test.vcf',
                 'created': '2018-03-30T00:09:36.563486Z',
                 'download_url': 'https://myawslink.com/member-files/direct-sharing-1337/1234/test.vcf?Signature=nope&Expires=1522390374&AWSAccessKeyId=nope',
                 'metadata': {'tags': ['bar'], 'description': 'foo'},
                 'source': 'direct-sharing-1337'}

        process_file(dfile, 'myaccesstoken', member, dfile['metadata'])

    @vcr.use_cassette('main/tests/fixtures/process_file_bz2.yaml',
                      record_mode='none')
    def test_process_file_bz2(self):
        """
        test process_file celery task
        """

        member = {"project_member_id": "1234"}
        dfile = {'id': 34567,
                 'basename': 'test.vcf.bz2',
                 'created': '2018-03-30T00:09:36.563486Z',
                 'download_url': 'https://myawslink.com/member-files/direct-sharing-1337/1234/test.vcf.bz2?Signature=nope&Expires=1522390374&AWSAccessKeyId=nope',
                 'metadata': {'tags': ['bar'], 'description': 'foo'},
                 'source': 'direct-sharing-1337'}

        process_file(dfile, 'myaccesstoken', member, dfile['metadata'])

    @vcr.use_cassette('main/tests/fixtures/process_file_gz.yaml',
                      record_mode='none')
    def test_process_file_gz(self):
        """
        test process_file celery task
        """

        member = {"project_member_id": "1234"}
        dfile = {'id': 34567,
                 'basename': 'test.vcf.gz',
                 'created': '2018-03-30T00:09:36.563486Z',
                 'download_url': 'https://myawslink.com/member-files/direct-sharing-1337/1234/test.vcf.gz?Signature=nope&Expires=1522390374&AWSAccessKeyId=nope',
                 'metadata': {'tags': ['bar'], 'description': 'foo'},
                 'source': 'direct-sharing-1337'}

        process_file(dfile, 'myaccesstoken', member, dfile['metadata'])
