# Nelson-Atkins public ticket details

The museum's `/events/` page supplies featured public performance links on `cart.nelson-atkins.org`. Its dynamic full calendar does not provide Event JSON-LD in the fetched HTML. The `tnew` adapter reads the selected performance's explicit year, clock, title and availability from its public detail container. It does not assert complete coverage of the full calendar.

`detail_hosts` is an explicitly reviewed, exact-host delegation. Other hosts, suffix lookalikes, credentials in URLs and non-HTTPS delegated links are excluded. Normal robots, challenge, rate-limit and redirect checks still apply; this is not a login or access workaround.

The More Dates selector can mix *different films or program titles*. Never clone the selected title onto those options. The index's actual links must lead to separately read performance pages. Missing years/clocks are unresolved, sold-out performances remain in the inventory, and ticket prices, end times and numeric age rules remain unknown when not supported. A museum's memory-care audience must remain visible in the excerpt.

The W46 live probe intentionally limited detail reads to one, yielding the November 12 memory-care tour with `SoldOut`; its partial/truncated status is expected, not full-calendar success. Two sanitized real-page fixtures also verify the November 13 Cinema Paradiso performance, selected-date isolation and public schema validity.

To probe without replacing the public inventory:

```sh
python3 scripts/collect_activities.py --only nelson --out /tmp/nelson-activities.json --cache /tmp/nelson-cache
```
