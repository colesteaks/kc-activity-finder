import test from "node:test";
import assert from "node:assert/strict";
import {
  hoursState,
  localClock,
  persistentActivities,
} from "../web/place-hours.mjs";
import { hasCoordinates, mapGroups, withinBounds } from "../web/map-data.mjs";
import { matches } from "../web/filters.mjs";
const rules = [
  { days: [0, 1, 2, 3, 4], opens: "10:00", closes: "16:00", scope: "visitor" },
];
function hours(extra = {}) {
  return {
    rules,
    exceptions: [],
    complete_week: true,
    timezone: "America/Chicago",
    checked_at: "2026-11-01T00:00:00Z",
    ...extra,
  };
}
function state(date, h = hours()) {
  return hoursState(h, new Date(date)).state;
}
test("numeric hours use Central time and exclusive closing boundary", () => {
  assert.equal(state("2026-11-06T16:00:00Z"), "within_hours");
  assert.equal(state("2026-11-06T22:00:00Z"), "outside_hours");
  assert.equal(state("2026-11-07T18:00:00Z"), "outside_hours");
});
test("closed exceptions override normal published hours", () => {
  const h = hours({
    exceptions: [{ date: "2026-11-06", closed: true, note: "Holiday" }],
  });
  assert.equal(state("2026-11-06T18:00:00Z", h), "outside_hours");
});
test("special exception hours replace the weekday schedule", () => {
  const h = hours({
    exceptions: [
      {
        date: "2026-11-07",
        closed: false,
        rules: [
          { days: [5], opens: "12:00", closes: "14:00", scope: "visitor" },
        ],
      },
    ],
  });
  assert.equal(state("2026-11-07T19:00:00Z", h), "within_hours");
  assert.equal(state("2026-11-07T21:00:00Z", h), "outside_hours");
});
test("gate hours do not imply the grounds are available after sunset", () => {
  const h = hours({
    rules: [
      { days: [5], opens: "07:00", closes: "sunset", scope: "grounds" },
      { days: [5], opens: "07:00", closes: "21:00", scope: "gate" },
    ],
  });
  assert.equal(state("2026-11-07T18:00:00Z", h), "daylight");
});
test("unknown, incomplete and stale hours never promise access", () => {
  assert.equal(state("2026-11-07T18:00:00Z", null), "unknown");
  assert.equal(state("2026-12-15T18:00:00Z"), "unknown");
  assert.equal(
    state("2026-11-07T18:00:00Z", hours({ complete_week: false })),
    "unknown",
  );
  assert.equal(
    state(
      "2026-11-07T18:00:00Z",
      hours({
        rules: [{ days: [5], opens: "07:00", closes: "21:00", scope: "gate" }],
      }),
    ),
    "unknown",
  );
});
test("overnight rule crosses season boundary and Central DST safely", () => {
  const rule = {
    days: [5],
    opens: "22:00",
    closes: "03:00",
    scope: "visitor",
    season_start: "04-01",
    season_end: "10-31",
  };
  const h = hours({ rules: [rule] });
  assert.equal(state("2026-11-01T07:30:00Z", h), "within_hours"); // repeated 01:30 CST
  assert.equal(localClock(new Date("2026-11-01T06:30:00Z")).weekday, 6);
  assert.equal(state("2026-11-01T09:00:00Z", h), "outside_hours");
});
test("winter seasons wrap the year; 24:00 has explicit meaning", () => {
  const h = hours({
    checked_at: "2026-12-31T00:00:00Z",
    rules: [
      {
        days: [0, 1, 2, 3, 4, 5, 6],
        opens: "00:00",
        closes: "24:00",
        scope: "grounds",
        season_start: "11-01",
        season_end: "04-14",
      },
    ],
  });
  assert.equal(state("2027-01-01T05:59:00Z", h), "within_hours");
});
test("map excludes missing/invalid coordinates and groups occurrences by offering", () => {
  const a = { id: "one", offering_id: "walk", geo: { lat: 39, lng: -94 } };
  assert.equal(hasCoordinates({ geo: { lat: NaN, lng: -94 } }), false);
  assert.equal(hasCoordinates({ geo: { lat: true, lng: 1 } }), false);
  const groups = mapGroups([
    a,
    { ...a, id: "two" },
    { ...a, id: "three", offering_id: "picnic" },
    { id: "unmapped" },
  ]);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].records.length, 3);
  assert.equal(groups[0].offerings.length, 2);
  assert.equal(
    withinBounds(a, { south: 38, north: 40, west: -95, east: -93 }),
    true,
  );
  assert.equal(withinBounds({}, {}), false);
});
test("place amenities apply to ongoing visits, not every special event there", () => {
  const places = [
    { id: "park", activities: [{ id: "hiking", name: "Walking and hiking" }] },
  ];
  const a = {
    title: "Park",
    place_id: "park",
    schedule: { kind: "evergreen" },
    ages: { all_ages: true },
    status: "listed",
  };
  const f = { amenity: "hiking", age_min: "", age_max: "" };
  assert.equal(matches(a, f, places), true);
  assert.equal(matches(a, { ...f, q: "hiking" }, places), true);
  assert.equal(
    matches({ ...a, schedule: { kind: "one_off" } }, f, places),
    false,
  );
  assert.deepEqual(persistentActivities({ ...a, place_id: null }, places), []);
});
