import { safeLink } from "./filters.mjs";

function fold(line) {
  if (line.length <= 73) return line;
  const parts = [line.slice(0, 73)];
  for (let index = 73; index < line.length; index += 72)
    parts.push(line.slice(index, index + 72));
  return parts.join("\r\n ");
}

function icsEscape(value) {
  return String(value || "")
    .replace(/\\/g, "\\\\")
    .replace(/\n/g, "\\n")
    .replace(/,/g, "\\,")
    .replace(/;/g, "\\;");
}

function stamp(date) {
  return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

export function activityToIcs(activity, now = new Date()) {
  const start = activity?.start || null;
  const day = activity?.date || activity?.schedule?.start_date || null;
  if (!start && !day) return null;
  const url = safeLink(activity.url);
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//What to do KC//Inventory//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${icsEscape(activity.id || activity.offering_id)}@what-to-do-kc`,
    `DTSTAMP:${stamp(now)}`,
  ];
  if (start) {
    const dt = new Date(start);
    if (Number.isNaN(dt.getTime())) return null;
    lines.push(`DTSTART:${stamp(dt)}`);
    if (activity.end) {
      const end = new Date(activity.end);
      if (!Number.isNaN(end.getTime())) lines.push(`DTEND:${stamp(end)}`);
    }
  } else {
    lines.push(`DTSTART;VALUE=DATE:${day.replace(/-/g, "")}`);
  }
  lines.push(
    `SUMMARY:${icsEscape(activity.title || "Activity")}`,
    `LOCATION:${icsEscape([activity.venue, activity.city].filter(Boolean).join(", "))}`,
  );
  if (url) lines.push(`URL:${url}`);
  lines.push(
    "END:VEVENT",
    "END:VCALENDAR",
  );
  return lines.map(fold).join("\r\n") + "\r\n";
}

export function downloadIcs(activity) {
  const body = activityToIcs(activity);
  if (!body || typeof document === "undefined") return false;
  const blob = new Blob([body], { type: "text/calendar" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${activity.offering_id || activity.id || "activity"}.ics`;
  link.click();
  URL.revokeObjectURL(link.href);
  return true;
}
