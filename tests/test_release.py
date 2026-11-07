import hashlib
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_release import REQUIRED, build, release_version
from verify_release import verify


def fixture():
    files = {name: b'Fictional payload for an archive test.\n' for name in REQUIRED}
    files.update({'VERSION': b'1.2.3\n',
                  'SKILL.md': b'---\nname: kc-activity-finder\ndescription: Fixture\nlicense: MIT\nmetadata:\n  version: "1.2.3"\n---\nFixture only.\n',
                  'CHANGELOG.md': b'# Changelog\n\n## [1.2.3] - 2030-01-01\n\nFictional release.\n\n## [1.2.2]\n\nOlder.\n'})
    return files


class ReleaseTests(unittest.TestCase):
    def test_version_tag_and_metadata_must_agree(self):
        files = fixture()
        self.assertEqual(release_version(files, 'v1.2.3'), '1.2.3')
        for tag in ('v1.2.4', '1.2.3', 'v1.2.3-beta'):
            with self.assertRaises(ValueError): release_version(files, tag)
        files['SKILL.md'] = files['SKILL.md'].replace(b'1.2.3', b'1.0.0')
        with self.assertRaises(ValueError): release_version(files)

    def test_invalid_versions_cannot_become_archive_paths(self):
        for version in ('01.2.3', '../1.2.3', '1.2', '1.2.3\nextra', '1.2.3;bad'):
            files = fixture(); files['VERSION'] = version.encode()
            with self.assertRaises(ValueError): release_version(files)

    def test_bundle_is_reproducible_and_includes_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = build(fixture(), '1' * 40, 1800000000, Path(tmp) / 'a', 'v1.2.3')
            second = build(fixture(), '1' * 40, 1800000000, Path(tmp) / 'b', 'v1.2.3')
            self.assertEqual(first.read_bytes(), second.read_bytes())
            manifest = verify(first)
            self.assertEqual(manifest['commit'], '1' * 40)
            self.assertEqual(set(manifest['files']), REQUIRED)
            checksum = (first.parent / 'SHA256SUMS').read_text().split()[0]
            self.assertEqual(checksum, hashlib.sha256(first.read_bytes()).hexdigest())
            self.assertEqual((first.parent / 'release-notes.md').read_text(), 'Fictional release.\n')

    def test_missing_runtime_file_blocks_build(self):
        files = fixture(); files.pop('data/primary-sources.txt')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Incomplete'): build(files, '1' * 40, 1800000000, tmp)

    def test_untracked_manifest_or_unsafe_path_cannot_enter_bundle(self):
        for name in ('../escape', '/absolute', 'nested/../../escape', '.git/config', 'RELEASE.json'):
            files = fixture(); files[name] = b'bad'
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError): build(files, '1' * 40, 1800000000, tmp)

    def test_tampered_payload_fails_manifest_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = build(fixture(), '1' * 40, 1800000000, tmp)
            with zipfile.ZipFile(archive) as source:
                members = [(m, source.read(m)) for m in source.infolist()]
            corrupt = Path(tmp) / 'corrupt.zip'
            with zipfile.ZipFile(corrupt, 'w') as target:
                for info, body in members:
                    target.writestr(info, b'tampered' if info.filename.endswith('/README.md') else body)
            with self.assertRaisesRegex(ValueError, 'hashes'): verify(corrupt)

    def test_duplicate_and_traversal_archive_entries_are_rejected(self):
        for unsafe in ('kc-activity-finder/../escape', '/escape', 'other-skill/SKILL.md'):
            with tempfile.TemporaryDirectory() as tmp:
                archive = Path(tmp) / 'unsafe.zip'
                with zipfile.ZipFile(archive, 'w') as target:
                    info = zipfile.ZipInfo(unsafe); info.external_attr = 0o100644 << 16
                    target.writestr(info, b'bad')
                with self.assertRaises(ValueError): verify(archive)

    def test_current_working_metadata_declares_released_version(self):
        files = {name: (ROOT / name).read_bytes() for name in ('VERSION', 'SKILL.md')}
        self.assertEqual(release_version(files), (ROOT / 'VERSION').read_text().strip())

    def test_recommended_commands_pin_explicit_github_tag_urls(self):
        version = (ROOT / 'VERSION').read_text().strip()
        expected = 'https://github.com/colesteaks/kc-activity-finder/tree/v' + version
        for name in ('README.md', 'references/installation.md'):
            commands = re.findall(r'npx skills@latest add (\S+)', (ROOT / name).read_text())
            self.assertTrue(commands, name)
            self.assertTrue(all(source == expected for source in commands), name)


if __name__ == '__main__': unittest.main()
