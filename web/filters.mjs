import { persistentActivities } from "./place-hours.mjs";
export function chicagoToday(now = new Date()) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Chicago",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}
export function addDays(day, n) {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}
export function windowDates(kind, today = chicagoToday()) {
  const day = new Date(`${today}T12:00:00Z`).getUTCDay();
  const sat = addDays(today, day === 0 ? -1 : 6 - day);
  if (kind === "weekend") return { from: sat, to: addDays(sat, 1) };
  if (kind === "month") return { from: today, to: addDays(today, 30) };
  if (kind === "ahead") return { from: addDays(today, 30), to: "" };
  return { from: today, to: "" };
}
export const PRESETS = [
  {
    id: "standouts",
    label: "Standouts",
    sort: "standout",
    filters: { include_offers: false },
  },
  {
    id: "kids",
    label: "Kids & family",
    sort: "standout",
    filters: { audience: "kids", include_offers: false },
  },
  {
    id: "free",
    label: "Likely free",
    sort: "date",
    filters: { free_likely: "yes", include_offers: false },
  },
  {
    id: "outdoors",
    label: "Outdoors",
    sort: "date",
    filters: { indoor_outdoor: "outdoor" },
  },
  {
    id: "day-trip",
    label: "Day trip",
    sort: "standout",
    filters: { drive_band: "1-2h" },
  },
  {
    id: "weekend-trip",
    label: "Weekend trip",
    sort: "standout",
    filters: { drive_band: "2-3.5h" },
  },
  {
    id: "amtrak",
    label: "Amtrak day trip",
    sort: "standout",
    filters: { amtrak: true, include_offers: false },
  },
  {
    id: "saved",
    label: "Saved",
    sort: "date",
    filters: { saved_only: true, include_offers: true },
  },
];

export function standoutScore(activity) {
  const score = activity?.hints?.standout_score;
  return Number.isInteger(score) ? score : 0;
}

function audienceMatches(activity, wanted) {
  const tags = activity?.hints?.audience || [];
  if (wanted === "kids")
    return tags.some((tag) => ["kids", "family", "all_ages"].includes(tag));
  return tags.includes(wanted);
}

export function matches(a, f, places = []) {
  if (!f.include_offers && isPromotion(a)) return false;
  if (f.audience && !audienceMatches(a, f.audience)) return false;
  if ((f.free_likely === "yes" || f.free_likely === true) && a.hints?.free_likely !== true)
    return false;
  if (f.indoor_outdoor && a.hints?.indoor_outdoor !== f.indoor_outdoor)
    return false;
  if (f.drive_band && a.geo_meta?.drive_band !== f.drive_band) return false;
  if (f.amtrak && !a.geo_meta?.amtrak_accessible) return false;
  if (f.saved_only) {
    const oid = a.offering_id || a.id;
    if (!(f.saved_ids instanceof Set) || !f.saved_ids.has(oid)) return false;
  }
  if (f.min_standout && standoutScore(a) < Number(f.min_standout)) return false;
  if (
    f.amenity &&
    !persistentActivities(a, places).some((x) => x.id === f.amenity)
  )
    return false;
  if (!f.unavailable && ["canceled", "postponed"].includes(a.status))
    return false;
  if (f.location && a.region !== f.location) return false;
  if (f.type && a.type !== f.type && !a.categories?.includes(f.type))
    return false;
  if (
    f.kind === "programs" &&
    ![
      "sports_season",
      "course",
      "camp",
      "recurring_program",
      "program_catalog",
    ].includes(a.schedule?.kind)
  )
    return false;
  if (f.kind && f.kind !== "programs" && a.schedule?.kind !== f.kind)
    return false;
  const low = a.schedule ? a.schedule.start_date : a.date;
  const high = a.schedule ? a.schedule.end_date : a.end_date;
  if (!low && !high && f.undated === false) return false;
  if (f.from && high && high < f.from) return false;
  if (f.to && low && low > f.to) return false;
  if (
    f.q &&
    ![
      a.title,
      a.city,
      a.venue,
      a.type,
      a.description,
      ...persistentActivities(a, places).map((x) => x.name),
    ]
      .join(" ")
      .toLowerCase()
      .includes(f.q.trim().toLowerCase())
  )
    return false;
  if (f.age_min !== "" || f.age_max !== "") {
    const r = a.ages;
    if (!r.all_ages && r.min === null && r.max === null) return f.unknown_ages;
    const low = f.age_min === "" ? 0 : Number(f.age_min),
      high = f.age_max === "" ? Infinity : Number(f.age_max);
    if (high < low || low > (r.max ?? Infinity) || high < (r.min ?? 0))
      return false;
  }
  return true;
}
export function isPromotion(a) {
  const title = a.title || "";
  const venue = a.venue || "";
  if (
    /workshop|\bclass\b|tasting|live music|concert|pottery|\btour\b|festival|comedy|trivia/i.test(
      title,
    )
  )
    return false;
  if (
    /happy hour refresh|half[- ]price happy hour|new .+ drinks|back at minsky|is back at minsky|\bhappy hour\b|\bdrink specials?\b|\b12-step\b|\brecovery group\b|\brooftop igloos?\b|\bhalf[- ]price\b|\btaco tuesday\b|\bdaily specials?\b|\bbrunch specials?\b/i.test(
      title,
    )
  )
    return true;
  return /minsky[’']s pizza|iron horse bar & grill|hammers dueling piano bar/i.test(
    venue,
  ) && /christmas at|happy hour|igloo|special|menu/i.test(title);
}
export function distinctOfferings(rows) {
  const grouped = new Map();
  for (const row of rows) {
    const id = row.offering_id || row.id;
    if (!grouped.has(id)) grouped.set(id, []);
    grouped.get(id).push(row);
  }
  return [...grouped.values()].map((group) => ({
    ...group[0],
    matching_dates: [
      ...new Set(
        group
          .filter((r) => !r.end_date || r.end_date === r.date)
          .map((r) => r.date)
          .filter(Boolean),
      ),
    ].sort(),
  }));
}
export function coverageStatus(sources, region = "") {
  const scoped = sources.filter((s) => !region || s.region === region);
  return {
    routes: scoped.length,
    contributing: scoped.filter((s) => s.events > 0).length,
    gaps: scoped.filter((s) => s.status !== "checked").length,
  };
}
export function sortedActivities(rows, sort) {
  return [...rows].sort((a, b) =>
    sort === "title"
      ? a.title.localeCompare(b.title)
      : sort === "new"
        ? (b.first_seen || "").localeCompare(a.first_seen || "") ||
          (a.start || "9999").localeCompare(b.start || "9999")
        : sort === "standout"
          ? standoutScore(b) - standoutScore(a) ||
            (a.start || "9999").localeCompare(b.start || "9999") ||
            a.title.localeCompare(b.title)
          : (a.start || "9999").localeCompare(b.start || "9999") ||
            a.title.localeCompare(b.title),
  );
}
export function safeLink(value) {
  try {
    const u = new URL(value);
    return ["https:", "http:"].includes(u.protocol) &&
      !u.username &&
      !u.password
      ? u.href
      : null;
  } catch {
    return null;
  }
}
