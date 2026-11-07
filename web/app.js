import { KIND_LABELS, scheduleLabel, activityHref } from "./activity-view.mjs";
import { hoursState, placeFor, persistentActivities } from "./place-hours.mjs";
import { hasCoordinates, withinBounds, mapGroups } from "./map-data.mjs";
import { ActivityMap } from "./map.mjs";
import {
  chicagoToday,
  windowDates,
  matches,
  sortedActivities,
  safeLink,
} from "./filters.mjs";
const $ = (id) => document.getElementById(id);
let data,
  visible = 30;
let mapView = false,
  mapController,
  mapBounds = null,
  focusId = null,
  mapRender = 0;
const form = $("filters"),
  inputs = {
    q: $("search"),
    location: $("location"),
    type: $("type"),
    kind: $("kind"),
    amenity: $("amenity"),
    undated: $("undated"),
    age_min: $("age-min"),
    age_max: $("age-max"),
    from: $("date-from"),
    to: $("date-to"),
    unknown_ages: $("unknown-ages"),
    unavailable: $("include-unavailable"),
  };
const day = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Chicago",
    month: "short",
    day: "numeric",
    year: "numeric",
  }),
  clock = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Chicago",
    hour: "numeric",
    minute: "2-digit",
  });
function el(tag, value = "", cls = "") {
  const e = document.createElement(tag);
  e.textContent = value;
  e.className = cls;
  return e;
}
function link(url, label) {
  const a = el("a", label),
    safe = safeLink(url);
  if (safe) {
    a.href = safe;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
  }
  return a;
}
function filters() {
  return Object.fromEntries(
    Object.entries(inputs).map(([k, e]) => [
      k,
      e.type === "checkbox" ? e.checked : e.value,
    ]),
  );
}
function card(a) {
  const c = el("article", "", "card"),
    top = el("div", "", "card-top");
  top.append(
    el(
      "span",
      data.taxonomy?.categories.find((c) => c.id === a.categories?.[0])
        ?.label || a.type,
      "card-type",
    ),
    el(
      "span",
      a.region === "Bentonville" ? "Northwest Arkansas" : a.region,
      "card-region",
    ),
  );
  c.append(top);
  const h = el("h3");
  const detail = el("a", a.title);
  detail.href = activityHref(a);
  h.append(detail);
  c.append(h);
  let when = scheduleLabel(a);
  if (a.start && a.schedule?.kind === "one_off" && !a.all_day)
    when += " · " + clock.format(new Date(a.start));
  c.append(
    el("p", when, "card-date"),
    el("p", a.venue + " · " + a.city, "card-venue"),
  );
  if (a.description)
    c.append(
      el(
        "p",
        a.description + (a.description.length === 200 ? "…" : ""),
        "card-description",
      ),
    );
  const tags = el("div", "", "card-meta");
  tags.append(el("span", a.ages.label, "tag"));
  if (a.schedule) tags.append(el("span", KIND_LABELS[a.schedule.kind], "tag"));
  if (a.status !== "scheduled")
    tags.append(el("span", a.status, "tag warning"));
  if (a.stale || Date.now() - new Date(a.checked_at) > 72 * 3600e3)
    tags.append(el("span", "Needs a fresh check", "tag warning"));
  if (a.conflicts?.length)
    tags.append(el("span", "Source conflict", "tag warning"));
  if (a.end_date !== a.date)
    tags.append(el("span", "Date range / series — confirm sessions", "tag"));
  if (a.ticket_status !== "unknown")
    tags.append(el("span", a.ticket_status, "tag"));
  if (a.price !== null)
    tags.append(
      el("span", `${a.currency || "Price"} ${a.price} · check fees`, "tag"),
    );
  c.append(tags);
  if (a.schedule?.kind === "evergreen") {
    const place = placeFor(a, data.places);
    c.append(el("p", hoursState(place?.hours).label, "place-hours"));
    const amenities = persistentActivities(a, data.places);
    if (amenities.length)
      c.append(
        el("p", amenities.map((x) => x.name).join(" · "), "place-amenities"),
      );
  }
  const bottom = el("div", "", "card-bottom");
  bottom.append(
    el("span", a.source_name),
    (() => {
      const aLink = el("a", "View activity →");
      aLink.href = activityHref(a);
      return aLink;
    })(),
  );
  c.append(bottom);
  if (hasCoordinates(a)) {
    const button = el("button", "Find on map", "text-button map-find");
    button.type = "button";
    button.addEventListener("click", () => {
      focusId = a.offering_id || a.id;
      mapView = true;
      render();
      $("map-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    c.append(button);
  }
  return c;
}
function render() {
  if (!data) return;
  const f = filters(),
    params = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) {
    if (k === "unknown_ages" || k === "undated") {
      if (!v) params.set(k, "0");
    } else if (k === "unavailable") {
      if (v) params.set(k, "1");
    } else if (v) params.set(k, v);
  }
  if ($("sort").value !== "date") params.set("sort", $("sort").value);
  if (mapView) params.set("view", "map");
  if (focusId) params.set("focus", focusId);
  if (mapBounds)
    params.set(
      "area",
      [mapBounds.south, mapBounds.west, mapBounds.north, mapBounds.east]
        .map((x) => x.toFixed(5))
        .join(","),
    );
  history.replaceState(
    null,
    "",
    location.pathname + (params.size ? "?" + params : "") + location.hash,
  );
  const invalid =
    (f.from && f.to && f.from > f.to) ||
    (f.age_min !== "" &&
      f.age_max !== "" &&
      Number(f.age_min) > Number(f.age_max));
  const rows = invalid
    ? []
    : sortedActivities(
        data.activities.filter(
          (a) =>
            matches(a, f, data.places) &&
            (!mapBounds || withinBounds(a, mapBounds)),
        ),
        $("sort").value,
      );
  $("result-count").textContent =
    `${rows.length.toLocaleString()} ${rows.length === 1 ? "good idea" : "good ideas"}`;
  $("results").replaceChildren(...rows.slice(0, visible).map(card));
  $("message").hidden = rows.length > 0;
  $("message").textContent = invalid
    ? "The start of a range needs to come before its end."
    : data.activities.length
      ? "Nothing matches just yet. Try a wider date range, another location, or include unspecified ages."
      : "No dated activities have been collected yet. See source coverage below.";
  $("more").hidden = rows.length <= visible;
  $("map-panel").hidden = !mapView;
  $("view-list").setAttribute("aria-pressed", String(!mapView));
  $("view-map").setAttribute("aria-pressed", String(mapView));
  $("map-clear-area").hidden = !mapBounds;
  if (mapView) {
    const revision = ++mapRender;
    mapController ||= new ActivityMap($("activity-map"), $("map-status"));
    const mapped = rows.filter(hasCoordinates),
      unique = new Set(mapped.map((a) => a.offering_id || a.id)).size;
    const unmapped = new Set(
      rows.filter((a) => !hasCoordinates(a)).map((a) => a.offering_id || a.id),
    ).size;
    $("map-status").textContent =
      `${unique} distinct activities at ${mapGroups(mapped).length} map points · ${unmapped} activities without verified coordinates${mapBounds ? " · Area filter active (unmapped listings excluded)" : ""}.`;
    mapController
      .update(rows, data.places || [], {
        preserveView: !!mapBounds,
        focus: focusId,
      })
      .catch((error) => {
        if (revision === mapRender)
          $("map-status").textContent =
            "The map is unavailable. All matching activities are still listed below.";
        console.error(error);
      });
  }
}
function coverage() {
  const gaps = data.sources.filter((s) => s.status !== "checked").length;
  $("coverage-summary").textContent =
    `${data.sources.length} sources checked · ${gaps} with gaps or collection notes`;
  $("horizon").textContent =
    `Collection window: ${data.horizon_start} through ${data.horizon_end} (seven calendar months). This is the search horizon, not a promise of events every month.`;
  for (const s of data.sources) {
    const row = el("div", "", "source-row"),
      h = el("strong");
    h.append(link(s.url, s.name));
    row.append(
      h,
      el(
        "p",
        `${s.region} · ${s.events} records · ${s.status} · ${s.visited_count} pages visited`,
      ),
      el("p", s.horizon_note),
    );
    if (s.truncated)
      row.append(
        el(
          "p",
          "Page or detail limit reached; collection is incomplete.",
          "source-errors",
        ),
      );
    if (s.unparsed_count)
      row.append(
        el(
          "p",
          `${s.unparsed_count} pages need a parser or manual date review.`,
          "source-errors",
        ),
      );
    for (const error of s.errors.slice(0, 3))
      row.append(el("p", error, "source-errors"));
    $("source-health").append(row);
  }
}
form.addEventListener("submit", (e) => e.preventDefault());
form.addEventListener("input", () => {
  focusId = null;
  visible = 30;
  document
    .querySelectorAll("[data-window]")
    .forEach((e) => e.classList.remove("active"));
  render();
});
$("sort").addEventListener("change", render);
$("more").addEventListener("click", () => {
  visible += 30;
  render();
});
$("reset").addEventListener("click", () => {
  mapBounds = null;
  focusId = null;
  form.reset();
  inputs.from.value = chicagoToday();
  inputs.to.value = "";
  $("sort").value = "date";
  visible = 30;
  document
    .querySelectorAll("[data-window]")
    .forEach((e) => e.classList.remove("active"));
  render();
});
$("location").addEventListener("change", () => {
  mapBounds = null;
  focusId = null;
  render();
});
$("view-list").addEventListener("click", () => {
  mapView = false;
  mapBounds = null;
  focusId = null;
  render();
});
$("view-map").addEventListener("click", () => {
  mapView = true;
  render();
});
$("map-search-area").addEventListener("click", () => {
  const b = mapController?.bounds();
  if (b) {
    mapBounds = b;
    focusId = null;
    visible = 30;
    render();
  }
});
$("map-clear-area").addEventListener("click", () => {
  mapBounds = null;
  mapController?.fit();
  render();
});
$("map-fit").addEventListener("click", () => {
  mapBounds = null;
  focusId = null;
  mapController?.fit();
  render();
});
document.querySelectorAll("[data-window]").forEach((b) =>
  b.addEventListener("click", () => {
    const w = windowDates(b.dataset.window);
    inputs.from.value = w.from;
    inputs.to.value = w.to;
    visible = 30;
    document
      .querySelectorAll("[data-window]")
      .forEach((e) => e.classList.toggle("active", e === b));
    render();
  }),
);
async function start() {
  try {
    const response = await fetch("./activities.json", { cache: "no-cache" });
    if (!response.ok) throw Error("Data unavailable");
    data = await response.json();
    if (!Array.isArray(data.activities) || !Array.isArray(data.sources))
      throw Error("Invalid data");
    for (const t of data.taxonomy?.categories || []) {
      const o = el("option", t.label);
      o.value = t.id;
      inputs.type.append(o);
    }
    for (const [value, label] of Object.entries(KIND_LABELS)) {
      const o = el("option", label);
      o.value = value;
      inputs.kind.append(o);
    }
    const amenities = new Map(
      (data.places || [])
        .flatMap((p) => p.activities)
        .map((a) => [
          a.id,
          {
            walking: "Walking & hiking",
            cycling: "Cycling",
            picnicking: "Picnicking",
            playground: "Playgrounds",
            camping: "Camping",
            museum: "History exhibits",
            hands_on_science: "Hands-on science",
            outdoor_art: "Outdoor art & nature",
          }[a.id] || a.name,
        ]),
    );
    for (const [value, label] of [...amenities].sort((a, b) =>
      a[1].localeCompare(b[1]),
    )) {
      const o = el("option", label);
      o.value = value;
      inputs.amenity.append(o);
    }
    const params = new URLSearchParams(location.search);
    mapView = params.get("view") === "map";
    focusId = params.get("focus");
    if (params.has("area")) {
      const b = params.get("area").split(",").map(Number);
      if (
        b.length === 4 &&
        b.every(Number.isFinite) &&
        b[0] >= -90 &&
        b[2] <= 90 &&
        b[0] < b[2] &&
        b[1] < b[3]
      )
        mapBounds = { south: b[0], west: b[1], north: b[2], east: b[3] };
    }
    inputs.from.value = chicagoToday();
    for (const [k, e] of Object.entries(inputs))
      if (params.has(k)) {
        if (e.type === "checkbox") e.checked = params.get(k) === "1";
        else e.value = params.get(k);
      }
    if (params.has("sort")) $("sort").value = params.get("sort");
    const hours = (Date.now() - new Date(data.updated_at)) / 36e5;
    $("freshness").textContent =
      `${data.activities.length.toLocaleString()} activities · Updated ${day.format(new Date(data.updated_at))} · ${hours > 72 ? "Collection needs a fresh check" : "Scheduled daily"}`;
    coverage();
    if (data.coverage_matrix) {
      const matrix = data.coverage_matrix.category_by_region;
      const gaps = matrix.filter((c) => c.status === "gap");
      $("coverage-summary").textContent +=
        ` · ${gaps.length} category/region gaps`;
      for (const region of data.taxonomy.regions) {
        const row = el("div", "", "source-row");
        row.append(el("strong", region));
        const missing = matrix
          .filter((c) => c.region === region && c.status === "gap")
          .map(
            (c) =>
              data.taxonomy.categories.find((t) => t.id === c.category)
                ?.label || c.category,
          );
        row.append(
          el(
            "p",
            "Source gaps: " +
              (missing.join(", ") ||
                "Every subject has at least one route; collection may still be incomplete."),
          ),
        );
        $("source-health").append(row);
      }
    }
    render();
  } catch (error) {
    $("freshness").textContent = "The collection is temporarily unavailable";
    $("result-count").textContent = "Let’s try again soon";
    $("message").hidden = false;
    $("message").textContent =
      "We couldn’t load the activity file. Refresh the page or use the source links in the project. Your filters stay in the URL.";
    console.error(error);
  }
}
start();
