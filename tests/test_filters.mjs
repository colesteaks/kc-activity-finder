import test from "node:test";
import assert from "node:assert/strict";
import {
  matches,
  windowDates,
  chicagoToday,
  safeLink,
} from "../web/filters.mjs";
const a = {
    title: "Concert",
    description: "Music",
    city: "Lawrence",
    venue: "Hall",
    region: "Lawrence",
    type: "Music",
    date: "2026-11-07",
    end_date: "2026-11-08",
    status: "scheduled",
    ages: { min: 18, max: null, all_ages: false },
  },
  f = {
    age_min: "",
    age_max: "",
    unknown_ages: true,
    unavailable: false,
    from: "",
    to: "",
  };
test("overlap includes a multi-day event", () =>
  assert.equal(
    matches(a, { ...f, from: "2026-11-08", to: "2026-11-09" }),
    true,
  ));
test("child range excludes explicit adult event", () =>
  assert.equal(matches(a, { ...f, age_min: "0", age_max: "5" }), false));
test("adult range includes adult event", () =>
  assert.equal(matches(a, { ...f, age_min: "25", age_max: "40" }), true));
test("unknown ages optional, never invented", () => {
  const b = { ...a, ages: { min: null, max: null, all_ages: false } };
  assert.equal(matches(b, { ...f, age_min: "3", unknown_ages: false }), false);
  assert.equal(matches(b, { ...f, age_min: "3" }), true);
});
test("canceled hidden by default", () =>
  assert.equal(matches({ ...a, status: "canceled" }, f), false));
test("region and case insensitive search combine", () => {
  assert.equal(matches(a, { ...f, location: "Lawrence", q: "MUSIC" }), true);
  assert.equal(matches(a, { ...f, location: "Columbia" }), false);
});
test("Sunday weekend includes current day", () =>
  assert.deepEqual(windowDates("weekend", "2026-11-08"), {
    from: "2026-11-07",
    to: "2026-11-08",
  }));
test("Chicago date near UTC midnight", () =>
  assert.equal(chicagoToday(new Date("2026-11-08T02:00:00Z")), "2026-11-07"));
test("unsafe links rejected", () => {
  assert.equal(safeLink("javascript:alert(1)"), null);
  assert.equal(safeLink("https://user:pass@example.com"), null);
  assert.equal(safeLink("https://example.com"), "https://example.com/");
});

test("evergreen has no invented date and can be hidden", () => {
  const trail = {
    ...a,
    start: null,
    date: null,
    end_date: null,
    schedule: { kind: "evergreen", start_date: null, end_date: null },
  };
  assert.equal(matches(trail, { ...f, from: "2027-01-01" }), true);
  assert.equal(matches(trail, { ...f, undated: false }), false);
});
test("exhibit overlaps mid-run date range", () => {
  const exhibit = {
    ...a,
    schedule: {
      kind: "exhibit",
      start_date: "2026-10-01",
      end_date: "2027-01-01",
    },
  };
  assert.equal(
    matches(exhibit, {
      ...f,
      from: "2026-12-01",
      to: "2026-12-05",
      kind: "exhibit",
    }),
    true,
  );
});
test("unknown season end is not replaced by first session date", () => {
  const season = {
    ...a,
    date: "2027-01-01",
    end_date: "2027-01-01",
    schedule: {
      kind: "sports_season",
      start_date: "2027-01-01",
      end_date: null,
    },
  };
  assert.equal(
    matches(season, { ...f, from: "2027-02-01", kind: "programs" }),
    true,
  );
});
