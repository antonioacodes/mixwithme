import fcntl
import importlib.util
import os
from pathlib import Path
import pwd
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('deploy_pull', Path(__file__).parents[1] / 'scripts/deploy_pull.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@unittest.skipIf(os.geteuid() == 0, 'Deploy must be exercised as a non-root user')
class DeployTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.origin = self.root / 'origin.git'
        self.source = self.root / 'source'
        self.checkout = self.root / 'checkout'
        self.git(self.root, 'init', '--bare', '--initial-branch=main', str(self.origin))
        self.git(self.root, 'clone', str(self.origin), str(self.source))
        self.configure(self.source)
        (self.source/'song.txt').write_text('v1\n')
        (self.source/'.gitignore').write_text('.env\ncache/\n')
        self.commit()
        self.git(self.root, 'clone', str(self.origin), str(self.checkout))
        self.configure(self.checkout)
        self.before = self.head(self.checkout)
        (self.source/'song.txt').write_text('v2\n')
        self.commit()
        self.target = self.head(self.source)

    def git(self, path, *args):
        return subprocess.check_output(['git', '-C', str(path), *args], stderr=subprocess.DEVNULL).decode().strip()

    def configure(self, path):
        self.git(path, 'config', 'user.name', 'Test')
        self.git(path, 'config', 'user.email', 'test@example.invalid')

    def commit(self):
        self.git(self.source, 'add', '-A')
        self.git(self.source, 'commit', '-m', 'fixture')
        self.git(self.source, 'push', 'origin', 'main')

    def head(self, path):
        return self.git(path, 'rev-parse', 'HEAD')

    def deploy(self, **kwargs):
        return module.update(self.checkout, kwargs.pop('sha', self.target),
                             {str(self.origin)}, pwd.getpwuid(os.geteuid()).pw_name, **kwargs)

    def refused(self):
        with self.assertRaises(module.DeployError):
            self.deploy()
        self.assertEqual(self.head(self.checkout), self.before)

    def test_fast_forward_and_idempotent_update(self):
        self.assertEqual(self.deploy()['status'], 'updated')
        self.assertEqual((self.checkout/'song.txt').read_text(), 'v2\n')
        self.assertEqual(self.deploy()['status'], 'unchanged')

    def test_check_only_does_not_change_checkout(self):
        self.assertEqual(self.deploy(check_only=True)['status'], 'checked')
        self.assertEqual(self.head(self.checkout), self.before)
        self.assertEqual((self.checkout/'song.txt').read_text(), 'v1\n')

    def test_dirty_tracked_file_preserved(self):
        (self.checkout/'song.txt').write_text('local changes')
        self.refused()
        self.assertEqual((self.checkout/'song.txt').read_text(), 'local changes')

    def test_untracked_file_preserved(self):
        (self.checkout/'untracked.txt').write_text('local')
        self.refused()
        self.assertTrue((self.checkout/'untracked.txt').exists())

    def test_staged_change_preserved(self):
        (self.checkout/'song.txt').write_text('staged')
        self.git(self.checkout, 'add', 'song.txt')
        self.refused()

    def test_divergent_local_commit_preserved(self):
        (self.checkout/'local.txt').write_text('local commit')
        self.git(self.checkout, 'add', '.')
        self.git(self.checkout, 'commit', '-m', 'local work')
        self.before = self.head(self.checkout)
        self.refused()

    def test_wrong_branch_refused(self):
        self.git(self.checkout, 'switch', '-c', 'work')
        self.refused()

    def test_wrong_origin_refused(self):
        self.git(self.checkout, 'remote', 'set-url', 'origin', str(self.root/'other.git'))
        self.refused()

    def test_stale_workflow_never_rolls_back(self):
        self.assertEqual(self.deploy(sha=self.before)['status'], 'skipped')
        self.assertEqual(self.head(self.checkout), self.before)

    def test_ignored_local_file_collision_refused(self):
        (self.checkout/'.env').write_text('private-local-data')
        (self.source/'.env').write_text('incoming')
        self.git(self.source, 'add', '--force', '.env')
        self.git(self.source, 'commit', '-m', 'add ignored path')
        self.git(self.source, 'push', 'origin', 'main')
        self.target = self.head(self.source)
        self.refused()
        self.assertEqual((self.checkout/'.env').read_text(), 'private-local-data')

    def test_ignored_data_not_in_diff_is_preserved(self):
        (self.checkout/'.env').write_text('keep')
        self.assertEqual(self.deploy()['status'], 'updated')
        self.assertEqual((self.checkout/'.env').read_text(), 'keep')

    def test_hidden_local_changes_refused(self):
        self.git(self.checkout, 'update-index', '--assume-unchanged', 'song.txt')
        (self.checkout/'song.txt').write_text('hidden edit')
        self.refused()

    def test_checkout_lock_refused(self):
        with (self.checkout/'.git/mixwithme-deploy.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.refused()

    def test_read_only_directory_refused(self):
        self.checkout.chmod(0o500)
        try:
            self.refused()
        finally:
            self.checkout.chmod(0o700)

    def test_wrong_user_refused(self):
        with self.assertRaises(module.DeployError):
            module.update(self.checkout, self.target, {str(self.origin)}, 'not-the-deploy-user')


if __name__ == '__main__':
    unittest.main()
