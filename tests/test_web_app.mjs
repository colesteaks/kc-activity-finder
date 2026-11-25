import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { activityToIcs } from "../web/ics.mjs";
import { hydrateBundle, loadInventory } from "../web/data-loader.mjs";
import { PRESETS, matches, sortedActivities, standoutScore } from "../web/filters.mjs";

test("date-only calendar export does not invent a clock time", () => {
  const ics = activityToIcs(
    {
      id: "trail",
      title: "Trail",
      date: "2026-12-01",
      url: "https://example.test/trail",
    },
    new Date("2026-11-24T18:00:00Z"),
  );
  assert.match(ics, /DTSTART;VALUE=DATE:20261201/);
  assert.doesNotMatch(ics, /DTSTART:\d{8}T/);
});

test("an activity with no explicit date is not exported", () => {
  assert.equal(activityToIcs({ id: "x", title: "Somewhere" }), null);
});

test("bundle hydration keeps explicit dates and caches the snapshot", async () => {
  const memory = new Map();
  const storage = {
    getItem: (key) => memory.get(key) || null,
    setItem: (key, value) => memory.set(key, value),
  };
  const bundle = {
    updated_at: "2026-11-24T12:00:00-06:00",
    activities: [
      {
        id: "jazz",
        title: "Jazz",
        date: "2026-12-18",
        url: "https://example.test/jazz",
        schedule: { kind: "one_off", start_date: "2026-12-18" },
      },
    ],
    sources: [],
  };
  let calls = 0;
  const data = await loadInventory({
    storage,
    fetchImpl: async () => {
      calls += 1;
      return { ok: true, json: async () => bundle };
    },
  });
  assert.equal(hydrateBundle(bundle).activities[0].schedule.sessions.length, 0);
  assert.equal(data.activities[0].title, "Jazz");
  const again = await loadInventory({
    storage,
    fetchImpl: async () => {
      throw Error("network should not be used");
    },
  });
  assert.equal(again.activities[0].id, "jazz");
  assert.equal(calls, 1);
});

test("hint presets and standout ordering are explicit", () => {
  assert.equal(PRESETS[0].id, "standouts");
  const row = {
    title: "Storytime",
    hints: { audience: ["kids", "family"], free_likely: true, standout_score: 70 },
    geo_meta: { drive_band: "0-30m" },
    ages: { min: null, max: null, all_ages: false },
    status: "scheduled",
  };
  const filters = {
    age_min: "",
    age_max: "",
    unknown_ages: true,
    unavailable: false,
    from: "",
    to: "",
    audience: "kids",
    free_likely: "yes",
  };
  assert.equal(matches(row, filters), true);
  assert.equal(matches(row, { ...filters, audience: "adults" }), false);
  assert.equal(standoutScore({}), 0);
  assert.equal(matches({ title: "Taco Tuesday", venue: "Grill" }, filters), false);

  assert.ok(PRESETS.some((p) => p.id === "amtrak"));
  assert.ok(PRESETS.some((p) => p.id === "saved"));
  const hermann = {
    offering_id: "h1",
    title: "Wurstfest",
    hints: { audience: ["all_ages"], standout_score: 85 },
    geo_meta: { drive_band: "2-3.5h", amtrak_accessible: true },
    ages: { min: null, max: null, all_ages: true },
    status: "scheduled",
  };
  assert.equal(matches(hermann, { ...filters, audience: "", free_likely: "", amtrak: true }), true);
  assert.equal(matches(row, { ...filters, audience: "", free_likely: "", amtrak: true }), false);
  assert.equal(
    matches(hermann, { ...filters, audience: "", free_likely: "", saved_only: true, saved_ids: new Set(["h1"]) }),
    true,
  );
  assert.equal(
    matches(hermann, { ...filters, audience: "", free_likely: "", saved_only: true, saved_ids: new Set() }),
    false,
  );
});

test("real v2 web/bundle.min.json hydrates, sorts, and matches every regional RSS feed slug", () => {
  const bundlePath = path.resolve("web/bundle.min.json");
  if (!fs.existsSync(bundlePath)) return;
  const raw = JSON.parse(fs.readFileSync(bundlePath, "utf8"));
  assert.equal(raw.version, 2);
  const hydrated = hydrateBundle(raw);
  assert.ok(hydrated.activities.length > 5000);
  const sample = hydrated.activities.find((a) => a.start);
  assert.ok(sample && !Number.isNaN(new Date(sample.start).getTime()));

  const byNew = sortedActivities(hydrated.activities.slice(0, 50), "new");
  const byStandout = sortedActivities(hydrated.activities.slice(0, 50), "standout");
  assert.equal(byNew.length, 50);
  assert.equal(byStandout.length, 50);

  for (const region of raw.taxonomy.regions) {
    const slug = region.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    assert.ok(fs.existsSync(path.resolve(`web/feeds/${slug}.xml`)), `Missing RSS feed for ${region}: ${slug}.xml`);
  }
});
