export const KIND_LABELS = {
  one_off: "One-time event",
  multi_day: "Multi-day event",
  exhibit: "Exhibit / limited run",
  sports_season: "Sports season",
  course: "Course / class series",
  camp: "Camp",
  recurring_program: "Recurring program",
  evergreen: "Ongoing place / activity",
  program_catalog: "Program catalog",
  date_range_unknown: "Published date range — sessions unconfirmed",
};
export function dateLabel(value) {
  return value
    ? new Intl.DateTimeFormat("en-US", {
        timeZone: "America/Chicago",
        month: "short",
        day: "numeric",
        year: "numeric",
      }).format(
        new Date(value.length === 10 ? value + "T12:00:00-06:00" : value),
      )
    : "Not published / not verified";
}
export function scheduleLabel(a) {
  const s = a.schedule;
  if (!s) return a.start ? dateLabel(a.start) : "Dates to confirm";
  if (s.kind === "evergreen") return "Ongoing place · check hours & conditions";
  if (!s.start_date && !s.end_date)
    return "Program dates to confirm with the organizer";
  if (s.start_date && s.end_date && s.start_date !== s.end_date)
    return dateLabel(s.start_date) + " – " + dateLabel(s.end_date);
  return (
    dateLabel(s.start_date || s.end_date) +
    (s.kind !== "one_off" && !s.end_date ? " · end date to confirm" : "")
  );
}
export function activityHref(a) {
  return "./activity.html?id=" + encodeURIComponent(a.offering_id || a.id);
}
export function findOffering(rows, id) {
  return rows.filter((a) => a.offering_id === id || a.id === id);
}
