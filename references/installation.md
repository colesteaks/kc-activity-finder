# Install, use and version the public skill

KC Activity Finder is distributed in the open [Agent Skills format](https://agentskills.io/specification): a `kc-activity-finder/` folder with `SKILL.md`, executable helpers and supporting resources. The public GitHub repository is the source and distribution point. A separate plugin/MCP server or app-store submission is not required to distribute this skill.

## Install the v1.0.1 release

Recommended: install a pinned GitHub tag using the [Skills CLI](https://github.com/vercel-labs/skills). Node.js/npm is needed for this installer, not for the Python-only core helpers:

```sh
npx skills@latest add https://github.com/colesteaks/kc-activity-finder/tree/v1.0.1 --skill kc-activity-finder
```

Choose the target agent and project/global scope in its prompts. For a project-local Codex installation without interactive prompts:

```sh
npx skills@latest add https://github.com/colesteaks/kc-activity-finder/tree/v1.0.1 \
  --skill kc-activity-finder --agent codex --copy --yes
```

This example installs into the current project's skill directory; it does not connect a ChatGPT app or automatically enable the skill in every chat. Other Agent Skills-compatible hosts use their own discovery paths/settings. Follow the host's installation instructions and restart/reload its skill discovery if needed. Browser/routing capabilities come from that host.

For a development checkout or manual installation:

```sh
git clone --branch v1.0.1 --depth 1 \
  https://github.com/colesteaks/kc-activity-finder.git
```

The repository root itself is the skill folder; keep all its supporting files together. For project-local Codex usage, place the folder at `.agents/skills/kc-activity-finder/`. Other hosts may use a different folder. Do not install just `SKILL.md`: the graph, schemas, Python modules and references are runtime dependencies.

Alternatively, [download the release ZIP](https://github.com/colesteaks/kc-activity-finder/releases/download/v1.0.1/kc-activity-finder-v1.0.1.zip) and [SHA256SUMS](https://github.com/colesteaks/kc-activity-finder/releases/download/v1.0.1/SHA256SUMS) from the same release. Verify, then extract the `kc-activity-finder/` directory into the location your host uses:

```sh
sha256sum --check SHA256SUMS
unzip kc-activity-finder-v1.0.1.zip
```

The ZIP is a complete, self-contained public project snapshot, without Git metadata, CI configuration, HTTP caches or local research. It includes the skill, source data, schemas, helpers, examples/tests and supporting static-site files so paths and validation still work after extraction. `RELEASE.json` identifies the exact source commit and hashes every payload file. It is not a bundled browser, model or dependency environment. A host accepting uploaded skill archives may use the ZIP; check its accepted format rather than assuming every chat UI supports archive installation.

## Run and verify

From the installed skill directory, use a virtual environment or your agent's Python environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/validate_repo.py
python3 scripts/day_trip_planner.py examples/day-trip-research.json \
  --output /tmp/day-trip-checks.json
python3 scripts/activity_pipeline.py report \
  examples/weekend-run.json /tmp/weekend-demo.md
```

Examples are fictional and remain labeled as such. For the full suite and collection/maintenance tools, also install `requirements-collector.txt`; JavaScript tests require Node.js. No API key is required by the core helpers. Live recommendations require current first-party research by the hosting agent, and strict driving limits require sourced routing estimates.

Then invoke the installed skill naturally:

> Use $kc-activity-finder to find activities for this weekend that fit our interests.

> Use $kc-activity-finder to compare day trips within two hours each way from Kansas City, then help us plan the best fit.

> Use $kc-activity-finder to find upcoming classes, races or programs worth registering for in advance.

## Releases and updates

[Latest release](https://github.com/colesteaks/kc-activity-finder/releases/latest) · [All releases](https://github.com/colesteaks/kc-activity-finder/releases) · [Changelog](../CHANGELOG.md)

The `v1.0.1` tag pins skill behavior, code, schemas and a source-data snapshot. Event availability, opening hours and third-party pages remain live facts: a versioned skill must still refresh them. Daily collection updates `main` and the public Pages inventory without creating a software release. Existing installations remain pinned until the owner deliberately installs a newer tag; a pinned source does not mean automatic tracking of `main`.

Use Semantic Versioning:

- **PATCH**: compatible bug fixes, corrections and evidence/maintenance improvements.
- **MINOR**: new compatible workflows, sources, capabilities or optional fields.
- **MAJOR**: breaking executable/schema contracts or materially incompatible workflow changes.

Do not move published tags or overwrite a published release's assets. Make a new version instead. Pin a full commit SHA rather than a tag if your deployment policy requires a content-addressed source. The repository is public and original project material is MIT licensed; retain attribution and third-party notices.

## Maintainer release procedure

1. Update `VERSION`, `SKILL.md`'s `metadata.version`, `CHANGELOG.md`, and the recommended installation examples for the new version. Run tests and inspect the diff. Keep private research and credentials outside Git.
2. Commit and push the release preparation to `main`. Wait for the normal validation workflow. The builder deliberately reads a **committed Git tree**, so uncommitted changes cannot leak into an artifact.
3. Locally verify the committed version if desired:

   ```sh
   python3 scripts/build_release.py --tag v1.0.1 --output /tmp/kc-release
   python3 scripts/verify_release.py \
     /tmp/kc-release/kc-activity-finder-v1.0.1.zip --smoke-test
   ```

4. Create an annotated tag on the reviewed commit and push it:

   ```sh
   git tag -a v1.0.1 -m 'KC Activity Finder v1.0.1'
   git push origin v1.0.1
   ```

5. The **Publish versioned skill** workflow validates the tag/version/metadata, runs tests, builds a deterministic ZIP and checksums, executes the unpacked helpers in a clean temporary directory, and verifies that a public installer records the requested Git tag and copies its runtime files. It uploads a draft release, downloads its assets to verify their checksums, then publishes it. No approval or model call is needed in that workflow; releases happen only on explicit version tags.
6. Confirm the published release targets the intended tag, assets download anonymously and the pinned installation works. Source and asset verification are required before announcing a release.

If a publish attempt leaves a draft release, inspect the failure before retrying. The workflow refuses to overwrite an existing release. Remove only the failed draft when appropriate and rerun the failed workflow; preserve the tag and all published releases. If a published release needs a fix, use a new patch version.
