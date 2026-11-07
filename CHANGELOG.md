# Changelog

Releases follow Semantic Versioning for the skill instructions, executable contracts and helpers. Daily activity observations are timestamped data, not new software releases.

## [1.0.0] - 2026-11-07

First public, versioned Agent Skills release of KC Activity Finder.

### Included

- First-party research workflow: source graph, deep sweep, capture, broader search, deduplication, party-fit ranking, adversarial review and recommendations.
- Broad adult, child and family discovery across Kansas City and regional destinations, with separate weekend and advance-registration workflows.
- Evergreen places, facility/ground/gate hours, seasonal rules, amenity restrictions and coordinate provenance.
- Destination-first day-trip planning, reusable prompts and deterministic driving/itinerary feasibility checks.
- Executable research ledger, schemas, scoring methodology, fictional examples, regression tests and maintenance instructions.
- Agent Skills metadata, MIT licensing for original project material, a self-contained ZIP, per-file release manifest and SHA-256 checksums.
- Tagged-release automation with validation and clean-extraction smoke checks before publication.

### Requirements and limits

- Python 3.11+ and `requirements.txt` for core helpers; live discovery needs host-provided browsing and optional routing tools. Install `requirements-collector.txt` for collection/maintenance tests and Node.js for JavaScript tests.
- Bundled activity/source data is a frozen, timestamped snapshot. Recheck current official facts or use the live site as discovery input; a version pin does not pin live event availability.
- The maintained authoritative graph starts with the preserved single newsletter seed. Approved supplemental routes and broader search improve coverage, but neither the release nor the automated collector promises exhaustive discovery.
- The artifact is an Agent Skills folder. Host installation/upload support varies; installing it does not automatically connect APIs, schedule automations, make bookings or add a ChatGPT app.
