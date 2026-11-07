#!/usr/bin/env python3
"""Check bundle integrity and optionally run the helpers in a clean extraction."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from build_release import NAME, REQUIRED, release_version


def verify(archive):
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        names = [m.filename for m in members]
        if len(names) != len(set(names)) or len(names) > 1000:
            raise ValueError('Duplicate archive entries or too many files')
        if sum(m.file_size for m in members) > 25 * 1024 * 1024:
            raise ValueError('Uncompressed bundle exceeds 25 MiB')
        for member in members:
            path = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            if (not path.parts or path.is_absolute() or '..' in path.parts or '\\' in member.filename
                    or path.parts[0] != NAME or len(path.parts) < 2 or not stat.S_ISREG(mode)):
                raise ValueError('Unsafe archive entry: ' + member.filename)
        files = {name.removeprefix(NAME + '/'): source.read(name) for name in names}
    if not REQUIRED <= set(files) or 'RELEASE.json' not in files:
        raise ValueError('Incomplete bundle')
    manifest = json.loads(files.pop('RELEASE.json'))
    version = release_version(files, manifest['tag'])
    if manifest['name'] != NAME or manifest['version'] != version or manifest['format'] != 'agent-skills':
        raise ValueError('Manifest identity mismatch')
    if not re.fullmatch(r'[0-9a-f]{40}', manifest['commit']):
        raise ValueError('Manifest needs a full commit SHA')
    hashes = {name: hashlib.sha256(body).hexdigest() for name, body in sorted(files.items())}
    if manifest['files'] != hashes:
        raise ValueError('Payload hashes do not match release manifest')
    return manifest


def smoke(archive):
    # Verify paths, file types and size before extracting any file.
    manifest = verify(archive)
    with tempfile.TemporaryDirectory(prefix='kc-skill-release-') as tmp:
        with zipfile.ZipFile(archive) as source:
            source.extractall(tmp)
        root = Path(tmp) / NAME
        commands = [
            [sys.executable, 'scripts/validate_repo.py'],
            [sys.executable, 'scripts/validate_public_data.py'],
            [sys.executable, 'scripts/day_trip_planner.py', 'examples/day-trip-research.json', '--output', str(Path(tmp) / 'trip.json')],
        ]
        for mode in ('weekend', 'signup'):
            commands.append([sys.executable, 'scripts/activity_pipeline.py', 'report', f'examples/{mode}-run.json', str(Path(tmp) / (mode + '.md'))])
        for command in commands:
            result = subprocess.run(command, cwd=root, capture_output=True, text=True)
            if result.returncode:
                raise ValueError('Extracted helper failed: ' + ' '.join(command) + '\n' + result.stdout[-2000:] + result.stderr[-2000:])
        for mode in ('weekend', 'signup'):
            if 'FICTIONAL DEMO' not in (Path(tmp) / (mode + '.md')).read_text():
                raise ValueError('Example report lost its fictional label')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--smoke-test', action='store_true')
    args = parser.parse_args()
    manifest = smoke(args.archive) if args.smoke_test else verify(args.archive)
    print(f"Verified {manifest['name']} v{manifest['version']} from {manifest['commit']}: {len(manifest['files'])} files" + ('; extracted helpers passed' if args.smoke_test else ''))


if __name__ == '__main__':
    main()
