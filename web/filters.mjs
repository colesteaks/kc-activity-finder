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
export function matches(a, f, places = []) {
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
export function sortedActivities(rows, sort) {
  return [...rows].sort((a, b) =>
    sort === "title"
      ? a.title.localeCompare(b.title)
      : sort === "new"
        ? b.first_seen.localeCompare(a.first_seen) ||
          (a.start || "9999").localeCompare(b.start || "9999")
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
