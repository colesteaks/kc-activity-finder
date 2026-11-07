import { safeLink, chicagoToday } from "./filters.mjs";
import { hoursState, placeFor, persistentActivities } from "./place-hours.mjs";
import { hasCoordinates } from "./map-data.mjs";
import {
  KIND_LABELS,
  scheduleLabel,
  dateLabel,
  findOffering,
  activityHref,
} from "./activity-view.mjs";

const root = document.getElementById("activity");
function el(tag, text = "", cls = "") {
  const e = document.createElement(tag);
  e.textContent = text;
  if (cls) e.className = cls;
  return e;
}
function external(url, label) {
  const a = el("a", label);
  const safe = safeLink(url);
  if (safe) {
    a.href = safe;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
  }
  return a;
}
function section(title) {
  const s = el("section", "", "detail-section");
  s.append(el("h2", title));
  return s;
}
function fact(dl, label, value) {
  dl.append(el("dt", label), el("dd", value ?? "Not published / not verified"));
}
function checkedLabel(value) {
  if (!value) return "Not recorded";
  return (
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/Chicago",
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value)) + " Central"
  );
}
function paragraph(parent, value) {
  parent.append(el("p", value));
}
function render(rows, all, taxonomy, places) {
  const today = chicagoToday();
  const upcoming = rows.filter((a) => !a.end_date || a.end_date >= today);
  const a = (upcoming.length ? upcoming : rows).sort((x, y) =>
    (x.start || "9999").localeCompare(y.start || "9999"),
  )[0];
  document.title = a.title + " — What to do, KC";
  root.replaceChildren();
  const header = el("header", "", "detail-hero");
  header.append(
    el("p", a.city + " · " + a.region, "eyebrow"),
    el("h1", a.title),
  );
  const labels = (a.categories || []).map(
    (id) => taxonomy?.categories.find((c) => c.id === id)?.label || id,
  );
  header.append(
    el("p", labels.join(" · "), "detail-category"),
    el("p", KIND_LABELS[a.schedule.kind], "detail-kind"),
  );
  if (a.stale || Date.now() - new Date(a.checked_at) > 72 * 3600e3)
    header.append(
      el(
        "p",
        "This listing needs a fresh check. Confirm directly with the source.",
        "detail-alert",
      ),
    );
  if (a.status !== "scheduled" && a.status !== "listed")
    header.append(el("p", "Source status: " + a.status, "detail-alert"));
  for (const conflict of a.conflicts || [])
    header.append(
      el("p", "Unresolved source conflict: " + conflict, "detail-alert"),
    );
  root.append(header);
  const grid = el("div", "", "detail-grid"),
    body = el("div"),
    aside = el("aside", "", "detail-key");
  const about = section("The activity");
  paragraph(
    about,
    a.description ||
      "The source lists this activity but has not supplied a summary. Follow the official link for the full description.",
  );
  const official = external(a.url, "Visit the official activity page ↗");
  official.className = "detail-button";
  about.append(official);
  body.append(about);
  const place = placeFor(a, places);
  if (place || hasCoordinates(a)) {
    const location = section("The place");
    if (place) {
      paragraph(location, place.name + " · " + place.address);
      location.append(
        external(place.source_url, "Official visitor information ↗"),
      );
      if (place.hours) {
        location.append(el("h3", "Published place hours"));
        paragraph(location, place.hours.text);
        paragraph(
          location,
          hoursState(place.hours).label + " · " + place.hours.notice,
        );
        paragraph(
          location,
          "Hours checked: " + checkedLabel(place.hours.checked_at),
        );
        location.append(
          external(place.hours.source_url, "Source for opening hours ↗"),
        );
        if (a.schedule.kind !== "evergreen")
          paragraph(
            location,
            "Place hours do not establish the event time, admission or access to individual facilities. Use the activity schedule.",
          );
        for (const exception of place.hours.exceptions)
          paragraph(location, exception.date + ": " + exception.note);
      } else
        paragraph(
          location,
          "Place opening hours have not been verified. Check the official visitor information.",
        );
      const amenities = persistentActivities(a, places);
      if (amenities.length) {
        location.append(el("h3", "Things to do here"));
        paragraph(
          location,
          "These are ongoing offerings. Weather, closures and facility-specific rules can affect access.",
        );
        const list = el("ul", "", "place-offerings");
        for (const item of amenities) {
          const li = el("li");
          li.append(el("strong", item.name));
          paragraph(
            li,
            {
              during_place_hours: "During published place hours",
              seasonal: "Seasonal availability",
              reservation_required: "Reservation required",
              admission_required: "Admission required",
              unknown: "Availability needs confirmation",
            }[item.availability] +
              " · " +
              item.note,
          );
          if (item.hours) {
            paragraph(
              li,
              item.hours.text + " · " + hoursState(item.hours).label,
            );
            li.append(external(item.hours.source_url, "Facility hours ↗"));
          }
          li.append(external(item.source_url, "Official details ↗"));
          list.append(li);
        }
        location.append(list);
      }
    }
    if (hasCoordinates(a)) {
      const mapLink = el(
        "a",
        "See this activity on the map →",
        "detail-button",
      );
      mapLink.href =
        "./?view=map&focus=" + encodeURIComponent(a.offering_id || a.id);
      location.append(mapLink);
      paragraph(location, a.geo.note);
      location.append(external(a.geo.source_url, "Location evidence ↗"));
    }
    body.append(location);
  }
  const schedule = section("When & how it works");
  paragraph(schedule, scheduleLabel(a));
  paragraph(schedule, a.schedule.note);
  const details = el("dl", "", "detail-facts");
  fact(details, "Activity format", KIND_LABELS[a.schedule.kind]);
  fact(details, "Operating hours", a.schedule.operating_hours);
  fact(
    details,
    "Attendance commitment",
    a.commitment.attendance === "unknown"
      ? null
      : a.commitment.attendance.replaceAll("_", " "),
  );
  fact(details, "Duration", a.commitment.duration);
  fact(details, "Equipment / prerequisites", a.commitment.equipment);
  schedule.append(details);
  if (a.schedule.recurrence) {
    paragraph(
      schedule,
      "Published recurrence: " +
        a.schedule.recurrence.rrule +
        " (" +
        a.schedule.recurrence.timezone +
        ")",
    );
    for (const d of a.schedule.recurrence.exdates)
      paragraph(schedule, "Excluded date: " + d);
  }
  for (const exception of a.schedule.exceptions)
    paragraph(schedule, "Exception / closure: " + exception);
  if (a.schedule.sessions.length) {
    const list = el("ul");
    for (const s of a.schedule.sessions) {
      list.append(
        el(
          "li",
          s.start +
            (s.end ? " — " + s.end : "") +
            (s.status ? " · " + s.status : ""),
        ),
      );
    }
    schedule.append(list);
  }
  if (rows.length > 1) {
    schedule.append(el("h3", "Published occurrences (" + rows.length + ")"));
    const list = el("ul", "", "detail-occurrences");
    for (const r of [...rows]
      .sort((x, y) => (x.start || "9999").localeCompare(y.start || "9999"))
      .slice(0, 100)) {
      list.append(
        el(
          "li",
          scheduleLabel(r) +
            (r.start && !r.all_day
              ? " · " +
                new Intl.DateTimeFormat("en-US", {
                  timeZone: "America/Chicago",
                  hour: "numeric",
                  minute: "2-digit",
                }).format(new Date(r.start))
              : "") +
            " · " +
            r.status,
        ),
      );
    }
    schedule.append(list);
    if (rows.length > 100)
      paragraph(schedule, "More dates are listed on the source page.");
  }
  body.append(schedule);
  const signup = section("Registration & cost");
  const rd = el("dl", "", "detail-facts");
  fact(
    rd,
    "Registration status",
    a.registration.status === "unknown"
      ? null
      : a.registration.status.replaceAll("_", " "),
  );
  fact(rd, "Registration opens", a.registration.opens_at);
  fact(rd, "Signup deadline", a.registration.deadline);
  fact(
    rd,
    "Source-listed price",
    a.price !== null
      ? `${a.currency || "Currency not supplied"} ${a.price}`
      : null,
  );
  signup.append(rd);
  paragraph(signup, a.registration.note);
  paragraph(
    signup,
    "A listed event, season or exhibit does not establish ticket stock, total admission cost or open registration. Confirm fees, prerequisites and the correct season before booking.",
  );
  if (a.registration.url)
    signup.append(external(a.registration.url, "Official registration ↗"));
  body.append(signup);
  const source = section("Sources & freshness");
  const evidence = [
    ...new Map(
      rows.flatMap((r) => r.sources || [r.evidence]).map((p) => [p.url, p]),
    ).values(),
  ];
  source.append(
    el(
      "p",
      a.source_name +
        " · " +
        (a.source_kind === "organizer"
          ? "organizer / provider"
          : "official calendar or discovery source"),
    ),
  );
  for (const p of evidence) {
    const item = el("p");
    item.append(external(p.url, "View source evidence ↗"));
    source.append(item);
  }
  paragraph(
    source,
    "Last checked: " + a.checked_at + " · First collected: " + a.first_seen,
  );
  paragraph(
    source,
    "Activity categories and formats marked as inferred are editorial classifications, not source eligibility rules.",
  );
  if (a.category_inferred || a.schedule.kind_inferred)
    paragraph(
      source,
      "This listing includes inferred classification. Its published dates and source links are retained separately.",
    );
  body.append(source);
  aside.append(el("h2", "At a glance"));
  const keys = el("dl", "", "detail-facts");
  fact(keys, "Where", a.venue + " · " + a.city);
  fact(keys, "When", scheduleLabel(a));
  fact(keys, "Ages", a.ages.label);
  fact(keys, "Source", a.source_name);
  fact(keys, "Time zone", "America/Chicago");
  aside.append(keys);
  paragraph(
    aside,
    "Check the organizer’s age policy, accessibility, current hours and conditions before going. Unknown details stay unknown.",
  );
  if (a.parent_id) {
    const parent = all.find((r) => r.id === a.parent_id);
    if (parent) {
      const l = el("a", "Part of: " + parent.title);
      l.href = activityHref(parent);
      aside.append(l);
    }
  }
  const share = el("button", "Copy activity link", "detail-button");
  share.type = "button";
  share.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      share.textContent = "Link copied";
    } catch {
      share.textContent = "Copy the address from your browser";
    }
  });
  aside.append(share);
  grid.append(body, aside);
  root.append(grid);
}
async function start() {
  try {
    const id = new URLSearchParams(location.search).get("id");
    if (!id) throw Error("missing-id");
    const response = await fetch("./activities.json", { cache: "no-cache" });
    if (!response.ok) throw Error("unavailable");
    const data = await response.json();
    const rows = findOffering(data.activities, id);
    if (!rows.length) {
      root.replaceChildren(
        el("h1", "This activity is no longer in the current collection."),
        el(
          "p",
          "It may have ended or changed. Browse current activities for the latest source listings.",
        ),
      );
      return;
    }
    render(rows, data.activities, data.taxonomy, data.places || []);
  } catch (error) {
    root.replaceChildren(
      el("h1", "We couldn’t load this activity."),
      el("p", "Check the link or return to the activity list."),
    );
    console.error(error);
  }
}
start();
