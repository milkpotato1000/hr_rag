"""P028 resource/doctor/preflight tests, without live services."""
import copy,json,os,socket,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from rag_package.workspace import init,doctor
from rag_package.llm.core import invoke,preview
from rag_package.llm.config import validate_config
from rag_package.connectors.drive_config import credential_path
from rag_package.drive_auth import protected_path
from rag_package.storage import RagError

class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.sample=self.root/'sample'
    def tearDown(self):self.tmp.cleanup()
    def test_resources_and_configuration_preflight(self):
        with patch('os.environ.get',side_effect=AssertionError('secret lookup')),patch.object(socket.socket,'connect',side_effect=AssertionError('network')):
            init(self.sample)
            for name in ('llm-local','llm-api'):
                c=validate_config(json.loads((self.sample/(name+'.json')).read_text()))
                for role in ('generation','evaluation'):
                    preview(c,role,[{'role':'user','content':'test'}])
                    result=invoke(c,role,[{'role':'user','content':'test'}],transport=lambda *a: self.fail('transport'),key_resolver=lambda *a:self.fail('key'))
                    self.assertEqual(result['error']['code'],'configuration_required');self.assertFalse(result['dispatch_attempted'])
                c=copy.deepcopy(c)
                for p in c['profiles'].values():p['identity']['validation_status']='user_configured_unverified'
                self.assertEqual(invoke(c,'generation',[{'role':'user','content':'test'}])['error']['code'],'configuration_required')
            r,code=doctor(self.sample/'fixed.json');self.assertEqual(code,3);self.assertEqual(r['status'],'needs_configuration');self.assertEqual(r['live_checks'],'not_checked')
        with self.assertRaises(RagError):init(self.sample)
        self.assertFalse((self.sample/'.git').exists())
    def test_doctor_offline_states(self):
        import importlib.metadata
        with patch('importlib.metadata.version',side_effect=importlib.metadata.PackageNotFoundError),patch('rag_package.workspace.storage_supported',return_value=True):
            r,code=doctor();self.assertEqual(code,0);self.assertEqual(r['optional_dependencies']['drive']['status'],'missing');self.assertEqual(r['optional_dependencies']['pdf']['status'],'missing')
            self.assertEqual(doctor(self.root/'absent')[1],2)
        with patch('importlib.metadata.version',return_value='WRONG'),patch('rag_package.workspace.storage_supported',return_value=True):
            r,code=doctor();self.assertEqual(code,0);self.assertEqual(r['optional_dependencies']['pdf']['status'],'version_mismatch')
        with patch('rag_package.workspace.storage_supported',return_value=False):self.assertEqual(doctor()[1],2)
    def test_installed_credential_boundaries(self):
        outside=self.root/'private';outside.mkdir(mode=0o700)
        with patch('rag_package.connectors.drive_config.WORKSPACE',None):
            for kind in ('directory','file'):
                repo=self.root/kind;repo.mkdir();marker=repo/'.git'
                if kind=='directory':marker.mkdir()
                else:marker.write_text('gitdir: /fake/never/read')
                private=repo/'private';private.mkdir(mode=0o700)
                with self.assertRaises(RagError):credential_path(str(private/'credential.json'))
            self.assertEqual(protected_path(outside/'credentials.json'),outside/'credentials.json')
            with self.assertRaises(RagError):credential_path(str(outside/'c.json'),workspace=self.root)
            linked=self.root/'linked';linked.symlink_to(outside,target_is_directory=True)
            with self.assertRaises(RagError):protected_path(linked/'credentials.json')
