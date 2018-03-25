from django.test import TestCase, RequestFactory
from django.conf import settings
from django.core.management import call_command
from open_humans.models import OpenHumansMember
from main.celery import read_reference
from main.celery_helper import vcf_header
import os


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

    def test_read_reference(self):
        """
        Test function to read the reference file.
        """
        REF_23ANDME_FILE = os.path.join(os.path.dirname(__file__),
                                        'fixtures/test_reference.txt')
        ref = read_reference(REF_23ANDME_FILE)
        self.assertEqual(ref, {'1': {'82154': 'A', '752566': 'G'}})

    def test_vcf_header(self):
        """
        Test function to create a VCF header
        """
        hd = vcf_header(
            source='23andme',
            reference='http://example.com',
            format_info=['<ID=GT,Number=1,Type=String,Description="GT">'])
        self.assertEqual(len(hd), 6)
        expected_header_fields = ["##fileformat",
                                  "##fileDate",
                                  '##source',
                                  '##reference',
                                  '##FORMAT',
                                  '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER' +
                                  '\tINFO\tFORMAT\t23ANDME_DATA']
        self.assertEqual([i.split("=")[0] for i in hd], expected_header_fields)
