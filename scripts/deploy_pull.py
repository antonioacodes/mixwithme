#!/usr/bin/env python3
"""Fast-forward a confirmed checkout, never discard local work. Python stdlib only."""
import base64
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys


class DeployError(RuntimeError):
    pass


def update(path, sha, allowed_origins, expected_user, check_only=False):
    user = pwd.getpwuid(os.geteuid()).pw_name
    if os.geteuid() == 0 or user != expected_user:
        raise DeployError('Use the configured non-root deploy user.')
    path = Path(path)
    if not path.is_absolute() or not path.is_dir():
        raise DeployError('Project path must be an existing absolute directory.')
    path = path.resolve()
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise DeployError('Expected commit must be a full SHA-1.')
    env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0',
           'GIT_SSH_COMMAND': 'ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15'}

    def git(*args, check=True):
        result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null',
                                 '-c', 'core.fsmonitor=false', *args],
                                cwd=path, env=env, capture_output=True, timeout=90)
        if check and result.returncode:
            # Git can include credential-bearing origin URLs in errors. Do not echo stderr.
            raise DeployError('Git command failed: ' + args[0] + '. Inspect the checkout/access on the VPS.')
        return result

    if Path(git('rev-parse', '--show-toplevel').stdout.decode().strip()).resolve() != path:
        raise DeployError('Configured path is not the repository root.')
    gitdir = Path(git('rev-parse', '--absolute-git-dir').stdout.decode().strip())
    if not os.access(path, os.W_OK | os.X_OK) or not os.access(gitdir, os.W_OK | os.X_OK):
        raise DeployError('Deploy user lacks write permission on checkout or Git directory.')
    lock_path = gitdir / 'mixwithme-deploy.lock'
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DeployError('Another deploy holds the checkout lock.') from exc
        if git('symbolic-ref', '--quiet', '--short', 'HEAD').stdout.strip() != b'main':
            raise DeployError('Checkout must already be on main; no automatic branch switch.')
        origin = git('remote', 'get-url', 'origin').stdout.decode().strip()
        if origin not in allowed_origins:
            raise DeployError('Origin does not match the expected repository.')
        for marker in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply'):
            if (gitdir / marker).exists():
                raise DeployError('An unfinished Git operation exists. Resolve it manually.')
        if git('status', '--porcelain=v1', '--untracked-files=all').stdout:
            raise DeployError('Local tracked or untracked changes found. Nothing will be overwritten.')
        flags = git('ls-files', '-v', '-z').stdout.split(b'\0')
        if any(entry and (entry[:1].islower() or entry.startswith(b'S ')) for entry in flags):
            raise DeployError('Assume-unchanged/skip-worktree flags could hide local changes.')
        # Verify existing tracked paths and parents before checkout can write to them.
        for raw in git('ls-files', '-z').stdout.split(b'\0'):
            if not raw:
                continue
            tracked = path / os.fsdecode(raw)
            parent = tracked.parent
            if tracked.is_symlink() or not parent.resolve().is_relative_to(path):
                raise DeployError('Symlinked tracked paths require manual review.')
            if not os.access(parent, os.W_OK | os.X_OK) or (tracked.exists() and not os.access(tracked, os.W_OK)):
                raise DeployError('Deploy user cannot update all tracked files/directories.')
        before = git('rev-parse', 'HEAD').stdout.decode().strip()
        git('fetch', '--no-tags', 'origin', 'refs/heads/main:refs/remotes/origin/main')
        latest = git('rev-parse', 'refs/remotes/origin/main').stdout.decode().strip()
        if latest != sha:
            return {'status': 'skipped', 'reason': 'A newer main exists; stale run will not deploy.', 'before': before}
        if git('merge-base', '--is-ancestor', before, sha, check=False).returncode:
            raise DeployError('Local commits diverge from main. Fast-forward refused.')
        # Check ignored files too: Git normally overwrites ignored files on merge.
        incoming = [os.fsdecode(p) for p in git('diff', '--name-only', '--diff-filter=ACRT', '-z', before, sha).stdout.split(b'\0') if p]
        ignored = [os.fsdecode(p) for p in git('ls-files', '--others', '--ignored', '--exclude-standard', '-z').stdout.split(b'\0') if p]
        for target in incoming:
            if any(target == item or target.startswith(item + '/') or item.startswith(target + '/') for item in ignored):
                raise DeployError('Incoming tracked path collides with an ignored local file.')
            parent = (path / target).parent
            while not parent.exists():
                parent = parent.parent
            if not parent.resolve().is_relative_to(path) or not os.access(parent, os.W_OK | os.X_OK):
                raise DeployError('Cannot safely create incoming path.')
        if check_only:
            return {'status': 'checked', 'before': before, 'target': sha,
                    'note': 'No worktree update; fetch and lock only.'}
        git('merge', '--ff-only', '--no-overwrite-ignore', sha)
        after = git('rev-parse', 'HEAD').stdout.decode().strip()
        if after != sha or git('status', '--porcelain=v1', '--untracked-files=all').stdout:
            raise DeployError('Post-update verification failed; no destructive recovery attempted.')
        return {'status': 'updated' if before != after else 'unchanged', 'before': before,
                'after': after}


def main():
    try:
        config = json.loads(base64.b64decode(sys.argv[1], validate=True))
        repo = config['repository']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            raise DeployError('Invalid repository name.')
        origins = {f'https://github.com/{repo}.git', f'https://github.com/{repo}',
                   f'git@github.com:{repo}.git', f'ssh://git@github.com/{repo}.git'}
        result = update(config['path'], config['sha'], origins, config['user'], config['check_only'])
        print(json.dumps(result))
    except OSError:
        print('Deploy refused: cannot access project files. Check path and permissions.', file=sys.stderr)
        return 1
    except (DeployError, ValueError, KeyError, IndexError, subprocess.TimeoutExpired) as exc:
        print('Deploy refused: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
