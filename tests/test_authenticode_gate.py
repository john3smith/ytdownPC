import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_authenticode import validate_policy,ReleaseBlocked

class AuthenticodePolicyTests(unittest.TestCase):
    def setUp(self):
        self.thumb='A'*40
        self.valid={'status':'Valid','signature_type':'Authenticode','timestamped':True,'code_signing_eku':True,'signer_thumbprint':self.thumb,'self_issued':False}
    def test_expected_signed_timestamped_identity(self):
        validate_policy(self.valid,self.thumb.lower())
    def test_unsigned(self):
        with self.assertRaises(ReleaseBlocked):validate_policy(dict(self.valid,status='NotSigned'),self.thumb)
    def test_untrusted(self):
        with self.assertRaises(ReleaseBlocked):validate_policy(dict(self.valid,status='NotTrusted'),self.thumb)
    def test_tampered(self):
        with self.assertRaises(ReleaseBlocked):validate_policy(dict(self.valid,status='HashMismatch'),self.thumb)
    def test_timestamp_missing(self):
        with self.assertRaises(ReleaseBlocked):validate_policy(dict(self.valid,timestamped=False),self.thumb)
    def test_other_signer(self):
        with self.assertRaises(ReleaseBlocked):validate_policy(self.valid,'B'*40)
    def test_no_code_signing_eku(self):
        with self.assertRaises(ReleaseBlocked):validate_policy(dict(self.valid,code_signing_eku=False),self.thumb)
    def test_catalog_only(self):
        with self.assertRaises(ReleaseBlocked):validate_policy(dict(self.valid,signature_type='Catalog'),self.thumb)
    def test_missing_expected_identity(self):
        with self.assertRaises(ReleaseBlocked):validate_policy(self.valid,None)
    def test_self_issued(self):
        with self.assertRaises(ReleaseBlocked):validate_policy(dict(self.valid,self_issued=True),self.thumb)

if __name__=='__main__':unittest.main()
