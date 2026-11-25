import test from "node:test";
import assert from "node:assert/strict";
import { activityToIcs } from "../web/ics.mjs";
import { hydrateBundle, loadInventory } from "../web/data-loader.mjs";
import { PRESETS, matches, standoutScore } from "../web/filters.mjs";

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
});
