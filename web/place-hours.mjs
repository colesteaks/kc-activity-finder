// Published schedules, not a live statement about closures or admission.
export function localClock(now, timezone = "America/Chicago") {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: timezone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(now)
      .map((x) => [x.type, x.value]),
  );
  const date = `${p.year}-${p.month}-${p.day}`;
  return {
    date,
    mmdd: date.slice(5),
    weekday: (new Date(date + "T12:00:00Z").getUTCDay() + 6) % 7,
    minute: Number(p.hour) * 60 + Number(p.minute),
  };
}
function inSeason(rule, mmdd) {
  if (!rule.season_start || !rule.season_end) return true;
  return rule.season_start <= rule.season_end
    ? mmdd >= rule.season_start && mmdd <= rule.season_end
    : mmdd >= rule.season_start || mmdd <= rule.season_end;
}
function minutes(value) {
  if (!/^(?:[01]\d|2[0-3]):[0-5]\d$|^24:00$/.test(value)) return null;
  const [h, m] = value.split(":").map(Number);
  return h * 60 + m;
}
export function hoursState(hours, now = new Date()) {
  const unknown = { state: "unknown", label: "Hours need confirmation" };
  if (!hours || !hours.rules?.length) return unknown;
  const age = now - new Date(hours.checked_at);
  if (!Number.isFinite(age) || age > 30 * 864e5 || age < -864e5)
    return { ...unknown, label: "Hours need a fresh check" };
  const clock = localClock(now, hours.timezone),
    exception = hours.exceptions?.find((x) => x.date === clock.date);
  if (exception?.closed)
    return {
      state: "outside_hours",
      label: "Closed by published exception",
      note: exception.note,
    };
  const rules = exception?.rules || hours.rules;
  const scope = rules.some((r) => r.scope === "grounds")
    ? "grounds"
    : "visitor";
  if (!rules.some((r) => r.scope === scope)) return unknown;
  let daylight = false,
    known = false;
  const previousDate = new Date(clock.date + "T12:00:00Z");
  previousDate.setUTCDate(previousDate.getUTCDate() - 1);
  const yesterday = {
    weekday: (previousDate.getUTCDay() + 6) % 7,
    mmdd: previousDate.toISOString().slice(5, 10),
    date: previousDate.toISOString().slice(0, 10),
  };
  const previousException = hours.exceptions?.find(
    (x) => x.date === yesterday.date,
  );
  for (const rule of rules.filter((r) => r.scope === scope)) {
    const opens = minutes(rule.opens),
      closes = minutes(rule.closes);
    if (rule.days.includes(clock.weekday) && inSeason(rule, clock.mmdd)) {
      known = true;
      if (opens === null || closes === null) {
        daylight = true;
        continue;
      }
      if (closes > opens && clock.minute >= opens && clock.minute < closes)
        return { state: "within_hours", label: "Within published hours" };
      if (closes < opens && clock.minute >= opens)
        return { state: "within_hours", label: "Within published hours" };
    }
    if (
      !exception &&
      !previousException &&
      opens !== null &&
      closes !== null &&
      closes < opens
    ) {
      if (
        rule.days.includes(yesterday.weekday) &&
        inSeason(rule, yesterday.mmdd) &&
        clock.minute < closes
      )
        return { state: "within_hours", label: "Within published hours" };
    }
  }
  if (daylight)
    return {
      state: "daylight",
      label: "Daylight schedule — check published hours",
    };
  return known || hours.complete_week
    ? { state: "outside_hours", label: "Outside published hours" }
    : unknown;
}
export function placeFor(row, places) {
  return places?.find((p) => p.id === row.place_id) || null;
}
export function persistentActivities(row, places) {
  return row.schedule?.kind === "evergreen"
    ? placeFor(row, places)?.activities || []
    : [];
}
