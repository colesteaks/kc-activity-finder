# Static hosting and daily collection

## Architecture and cost

GitHub Actions → reviewed sources → flat `web/activities.json` → GitHub Pages.

The site is plain HTML, CSS and JavaScript. It fetches one JSON file and filters entirely in the browser. There is no database, server API, paid search API, LLM call or secret needed for normal operation. Collection uses Python, Beautiful Soup, dateutil and standard HTTP. Daily LLM token usage is zero. GitHub Actions minutes, cache storage and private-repository Pages eligibility still follow the account's plan. Public visitors receive only `web/`, never the private repository or research files.

The scheduled workflow runs daily at **11:23 UTC** (5:23 a.m. Central Standard Time / 6:23 a.m. Central Daylight Time). GitHub schedules are best-effort and may be delayed. The exact requested horizon is seven calendar months ahead, ensuring at least six months across short/long months. Sources often publish a shorter schedule; the UI explicitly distinguishes the requested horizon from published coverage.

## Files and trust

| File | Purpose |
| --- | --- |
| `data/primary-sources.txt` | Original supplied seed, preserved byte-for-byte |
| `data/source-graph.json` | Curated authoritative graph; never overwritten by daily discovery |
| `data/collection-sources.json` | Reviewed supplements with source ownership, region, route, adapter and request limits |
| `data/generated-source-graph.json` | Deterministic daily view of approved sources and observed outbound relationships |
| `data/source-proposals.json` | Unreviewed discovered producer links and advertised RSS/iCal feed proposals |
| `web/activities.json` | Public event facts and source-health ledger; no private party information |
| `.collector-cache/` | Ignored HTTP response cache; restored via Actions cache, never published |

New proposals do not automatically become trusted sources. Review ownership, region, explicit dates, robots rules, feed behavior and attribution before adding a registry entry. A newsletter link is a lead, not evidence that an event is current. Existing seed provenance is never rewritten to make a supplement look supplied.

The hosted list is a **discovery inventory**, not an automatically verified recommendation shortlist. The original skill's deeper browsing, request-specific scoring and adversarial review remain useful for personalized recommendations. Deterministic scripts cannot reproduce semantic web search or reliably assess every age policy.

## Daily workflow

`.github/workflows/activities.yml` supports schedule, manual Run workflow and pushes changing site/collector files. Scheduled/manual refreshes:

1. Verify seed hash, visit approved pages, and discover source/feed proposals.
2. Fetch structured event feeds and pages, including pagination and bounded detail leaves. Month calendars are queried across the seven-month horizon where supported.
3. Normalize dates to America/Chicago, retain explicit age guidance, classify category heuristically, preserve source links, deduplicate exact occurrences and quarantine malformed dates.
4. Preserve missing future records as stale rather than deleting them; retain canceled status and source conflicts. Never assume a disappeared listing was canceled.
5. Validate data and commit the small generated JSON files to main.
6. Upload only `web/` and deploy using the official GitHub Pages actions.

Normal source responses are capped at 6 MB and requests time out after 20 seconds. Workers are limited to three, pagination to twelve pages and detail crawling to per-source limits. Requests pause between pages. HTTP ETags/Last-Modified support conditional requests; no API/model token is involved. Blocked sources become visible health gaps. A wholly failed fetch run does not replace the previous file. A partially successful run preserves old records with their original observation times and stale labels.

## Handling calendar blocks and format changes

Use the least expensive supported public interface:

1. Advertised iCal/RSS export or official JSON/API feed.
2. Event JSON-LD or embedded application JSON (decoded as data, never evaluated JavaScript).
3. A site-specific HTML parser with explicit dates and years.
4. A normal browser for JavaScript rendering, if the site permits automation. This costs runner minutes, not model tokens, but is not needed for existing embedded-data adapters.
5. Another permitted official calendar, organizer-linked ticket provider, or syndication partner. Keep secondary listings labeled as leads until confirmed.

Do not bypass logins, CAPTCHA, robots disallows, rate limits, or denied access using identity/IP rotation. A 403, 429 or robots denial needs an offered alternative, permission or a different source. Request access if a valuable feed has no public option. A changed parser is an ordinary maintenance task; retries cannot fix a missing date or a wrong-year page.

Currently supported adapters: Tribe REST events, nested JSON-LD, selected explicit Columbia CVB HTML dates, and Next.js serialized zoo/museum event data. Feed discovery detects RSS/iCal proposals; **RSS/iCal importers are not yet implemented**. The generated graph includes proposal provenance, not a claim those feeds were collected. Some current routes remain partial and are exposed in the website's source-health section.

## Filters and source facts

Age filtering uses overlap with the requested age interval; it is not an assertion that every member of a mixed group is eligible. Explicit all-ages policies are distinct from unknown age guidance. Unknown ages are included by default with a visible label and can be excluded. Category is inferred from source title/category, never advertised as an organizer rule. Some prices and ticket states in structured markup may be defaults: the UI links to the source and asks visitors to confirm current availability and fees.

Date ranges may describe a series rather than daily sessions; do not expand a range into invented occurrences. The site marks these and links to the actual schedule. Different occurrence dates stay separate. Cancellation prefixes in organizer titles override an unchanged schema default. Assertions about actual stock are never inferred from an event being scheduled.

## Enable and operate

Repository Settings → Pages → Source → **GitHub Actions**. Keep the repository private if desired; do not change visibility to fix a Pages error. The account must have a plan that supports Pages for private repositories. The workflow has explicit Pages/write and OIDC permissions. Organization policy or branch protection may still require an administrator to permit bot commits; failed runs expose that error instead of silently stopping updates.

For an immediate refresh: Actions → **Collect activities and publish site** → Run workflow → refresh=true. For a deployment without scraping: refresh=false. Schedules run from the default branch. Scheduled workflow inactivity policies and billing limits are controlled by GitHub; check the Actions page if the site's timestamp is stale.

Local commands:

```sh
python3 -m pip install -r requirements.txt -r requirements-collector.txt
python3 scripts/refresh_sources.py
python3 scripts/collect_activities.py
python3 scripts/validate_public_data.py
python3 -m unittest discover -s tests -v
node --test tests/test_filters.mjs
python3 -m http.server --directory web
```

Check new adapters against representative raw source fixtures, wrong-year pages, offsets/DST, missing dates, cancellations, parent/child sessions, source failures and strict age policies. A live source smoke test complements offline tests. Review proposals periodically; an unattended parser is cheap, but maintaining healthy source coverage still takes occasional attention.

## Domain

Domain discovery on November 7, 2026 returned `what-to-do-kc.com`, `whattodokc.com`, `kcactivityfinder.com` and `whatsonkc.com` available at a quoted $12.03 registration and $12.03 renewal for one year through Vercel Registrar (non-premium). Availability and pricing may change. No domain has been purchased.

After the owner selects and purchases a domain, add it in repository Pages settings, configure the exact DNS records returned/documented by GitHub at the registrar, verify ownership and enable HTTPS after certificate provisioning. Purchasing a domain does not require hosting on that registrar's platform. Do not commit a `web/CNAME` until ownership and DNS are ready.
