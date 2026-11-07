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
