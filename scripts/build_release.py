#!/usr/bin/env python3
"""Build a reproducible Agent Skills ZIP from one committed Git tree (stdlib only)."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
NAME = 'kc-activity-finder'
REPOSITORY = 'https://github.com/colesteaks/kc-activity-finder'
SEMVER = r'(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)'
REQUIRED = {
    'VERSION', 'SKILL.md', 'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'CHANGELOG.md',
    'requirements.txt', 'requirements-collector.txt', 'agents/openai.yaml',
    'data/primary-sources.txt', 'data/source-graph.json', 'data/workflow.json',
    'scripts/activity_pipeline.py', 'scripts/day_trip_planner.py', 'scripts/validate_repo.py',
    'schemas/query.schema.json', 'schemas/day-trip.schema.json', 'references/installation.md',
}


def release_version(files, tag=None):
    version = files['VERSION'].decode().strip()
    if not re.fullmatch(SEMVER, version):
        raise ValueError('VERSION must be a stable MAJOR.MINOR.PATCH version without leading zeroes')
    skill = files['SKILL.md'].decode()
    frontmatter = skill.split('---', 2)[1] if skill.startswith('---\n') else ''
    if not re.search(r'^name: kc-activity-finder$', frontmatter, re.M):
        raise ValueError('Skill name must match the release folder name')
    if not re.search(r'^  version: "' + re.escape(version) + '"$', frontmatter, re.M):
        raise ValueError('SKILL.md metadata.version must match VERSION')
    if not re.search(r'^license: MIT$', frontmatter, re.M):
        raise ValueError('The skill must declare its bundled MIT license')
    if tag is not None and tag != 'v' + version:
        raise ValueError('Release tag must equal v' + version)
    return version


def notes_for(files, version):
    changelog = files['CHANGELOG.md'].decode()
    match = re.search(r'^## \[' + re.escape(version) + r'\][^\n]*\n(.*?)(?=^## \[|\Z)', changelog, re.M | re.S)
    if not match:
        raise ValueError('CHANGELOG.md needs a section for this version')
    return match.group(1).strip() + '\n'


def committed_files(root, ref):
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}'], cwd=root, text=True).strip()
    epoch = int(subprocess.check_output(['git', 'show', '-s', '--format=%ct', commit], cwd=root, text=True))
    archive = subprocess.check_output(['git', 'archive', '--format=tar', commit], cwd=root)
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for member in source:
            if member.isdir():
                continue
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or '\\' in member.name:
                raise ValueError('Unsafe source path')
            # Do not distribute CI configuration as an agent's runtime instructions.
            if path.parts[0].startswith('.'):
                continue
            if not member.isfile():
                raise ValueError('Release payload must contain regular files only: ' + member.name)
            files[member.name] = source.extractfile(member).read()
    return files, commit, epoch


def build(files, commit, epoch, output, tag=None):
    missing = REQUIRED - set(files)
    if missing:
        raise ValueError('Incomplete skill payload: ' + ', '.join(sorted(missing)))
    version = release_version(files, tag)
    notes = notes_for(files, version)
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Expected a full source commit SHA')
    for name in files:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or path.parts[0].startswith('.'):
            raise ValueError('Unsafe payload path: ' + name)
    if 'RELEASE.json' in files:
        raise ValueError('RELEASE.json is generated, never copied from the source tree')
    manifest = {'format': 'agent-skills', 'name': NAME, 'version': version, 'tag': 'v' + version,
                'repository': REPOSITORY, 'commit': commit,
                'source_committed_at': datetime.fromtimestamp(epoch, timezone.utc).isoformat(),
                'files': {name: hashlib.sha256(body).hexdigest() for name, body in sorted(files.items())}}
    payload = dict(files, **{'RELEASE.json': (json.dumps(manifest, indent=2) + '\n').encode()})
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'{NAME}-v{version}.zip'
    stamp = datetime.fromtimestamp(max(epoch, 315532800), timezone.utc).timetuple()[:6]
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
        for name, body in sorted(payload.items()):
            info = zipfile.ZipInfo(NAME + '/' + name, date_time=stamp)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, body, compresslevel=9)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS').write_text(f'{checksum}  {archive.name}\n')
    (output / 'release-notes.md').write_text(notes)
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='HEAD', help='Committed tree to package; working changes are excluded')
    parser.add_argument('--tag', help='Require this tag to match VERSION and skill metadata')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    files, commit, epoch = committed_files(ROOT, args.ref)
    print(build(files, commit, epoch, args.output, args.tag))


if __name__ == '__main__':
    main()
