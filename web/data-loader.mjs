const KEY = "kc-activity-bundle-v2";
const TIME_OFF_RE = /^(\d{2}:\d{2})([+-]\d{2})$/;

function ageLabel(ages = {}) {
  if (ages.label) return ages.label;
  if (ages.all_ages) return "All ages (source stated)";
  if (ages.min == null && ages.max == null) return "Age guidance not supplied";
  if (ages.min != null && ages.max != null) return `Ages ${ages.min}–${ages.max}`;
  if (ages.min != null) return `Ages ${ages.min}+`;
  return `Ages up to ${ages.max}`;
}

function decodeStart(dateVal, timePart) {
  if (!timePart) return null;
  const match = TIME_OFF_RE.exec(timePart);
  if (match && dateVal) return `${dateVal}T${match[1]}:00${match[2]}:00`;
  return timePart;
}

function decodeAges(ageTuple) {
  if (!Array.isArray(ageTuple) || !ageTuple.length) {
    return { min: null, max: null, all_ages: false };
  }
  if (ageTuple[0]) return { min: 0, max: null, all_ages: true };
  return {
    min: ageTuple[1] ?? null,
    max: ageTuple[2] ?? null,
    all_ages: false,
  };
}

function tableAt(tbl, idx) {
  return Array.isArray(tbl) && Number.isInteger(idx) && idx >= 0 && idx < tbl.length
    ? tbl[idx]
    : null;
}

function hydrateRow(row) {
  return {
    conflicts: [],
    ...row,
    schedule: {
      kind: row.schedule?.kind || "one_off",
      start_date: row.schedule?.start_date ?? row.date ?? null,
      end_date: row.schedule?.end_date ?? row.end_date ?? null,
      sessions: row.schedule?.sessions || [],
      recurrence: row.schedule?.recurrence || null,
    },
    evidence: row.evidence || {
      url: row.url,
      format: row.evidence_format || "bundle",
    },
    ages: {
      min: null,
      max: null,
      all_ages: false,
      ...(row.ages || {}),
      label: ageLabel(row.ages || {}),
    },
  };
}

export function hydrateBundle(bundle) {
  if (!Array.isArray(bundle.occurrences)) {
    return {
      ...bundle,
      activities: (bundle.activities || []).map(hydrateRow),
    };
  }
  const sourceNames = Object.fromEntries(
    (bundle.sources || []).map((source) => [source.id, source.name]),
  );
  const placeMap = Object.fromEntries(
    (bundle.places || []).map((place) => [place.id, place]),
  );
  const isV2 = bundle.version === 2 && bundle.tables && typeof bundle.tables === "object";
  const tables = bundle.tables || {};

  const offerings = isV2
    ? (bundle.offerings || []).map((row) => {
        const at = (i, fallback = null) =>
          i < row.length && row[i] !== null && row[i] !== undefined ? row[i] : fallback;
        const skCode = at(7, 0);
        const source_kind =
          skCode === 1 ? "organizer" : skCode === 2 ? "official-calendar" : "sensor";
        const freeRaw = at(13, null);
        const free_likely = freeRaw === 1 ? true : freeRaw === 0 ? false : null;
        const geoPt = at(19, null);
        const place_id = at(21, null);
        const placeGeo = place_id ? placeMap[place_id]?.geo : null;
        const url = at(2);
        const ranged = at(23, null);
        const kind = tableAt(tables.kinds, at(10)) || "one_off";
        const source_id = tableAt(tables.sources, at(6));
        return {
          offering_id: at(0),
          title: at(1),
          url,
          venue: tableAt(tables.venues, at(3)) || "",
          city: tableAt(tables.cities, at(4)) || "",
          region: tableAt(tables.regions, at(5)) || "",
          source_id,
          source_name: sourceNames[source_id] || source_id,
          source_kind,
          categories: (at(8, []) || [])
            .map((i) => tableAt(tables.categories, i))
            .filter(Boolean),
          type: tableAt(tables.types, at(9)) || "Other",
          schedule: {
            kind,
            start_date: Array.isArray(ranged) ? ranged[0] ?? null : null,
            end_date: Array.isArray(ranged) ? ranged[1] ?? null : null,
          },
          hints: {
            labeled_estimate: true,
            standout_score: at(11, 0),
            audience: (at(12, []) || [])
              .map((i) => tableAt(tables.audiences, i))
              .filter(Boolean),
            free_likely,
            indoor_outdoor: tableAt(tables.io, at(14)) || "unknown",
          },
          geo_meta: {
            drive_band: tableAt(tables.bands, at(15)),
            corridor: tableAt(tables.corridors, at(16)),
            amtrak_accessible: Boolean(at(17, 0)),
          },
          first_seen: at(18, ""),
          geo: Array.isArray(geoPt) && geoPt.length >= 2
            ? {
                lat: geoPt[0],
                lng: geoPt[1],
                precision: placeGeo?.precision || "source_point",
                source_url: placeGeo?.source_url || url,
                note: placeGeo?.note || "Coordinates supplied by source listing.",
              }
            : null,
          ages: decodeAges(at(20, null)),
          place_id,
          price: at(22, null),
          conflict_count: at(24, 0),
          ticket_status: "unknown",
        };
      })
    : bundle.offerings || [];

  const activities = bundle.occurrences.map((occ) => {
    const offer = offerings[occ[0]] || {};
    const date = occ[1] || null;
    const endDate = occ[2] || date;
    const start = isV2 ? decodeStart(date, occ[3] || "") : occ[3] || null;
    const kind = offer.schedule?.kind || "one_off";
    const ranged = kind !== "one_off";
    const stale = Boolean(occ[5]);
    return hydrateRow({
      ...offer,
      id: `${offer.offering_id || occ[0]}:${date || "undated"}`,
      date,
      end_date: endDate,
      start,
      end: null,
      status: occ[4] || "scheduled",
      all_day: !start,
      stale,
      first_seen: offer.first_seen || "",
      checked_at: offer.checked_at || (stale ? null : bundle.updated_at || null),
      source_name: offer.source_name || sourceNames[offer.source_id] || offer.source_id,
      schedule: {
        ...(offer.schedule || {}),
        kind,
        start_date: ranged ? offer.schedule?.start_date || date : date,
        end_date: ranged ? offer.schedule?.end_date || endDate : endDate,
        sessions: [],
      },
    });
  });
  return { ...bundle, activities };
}

export async function loadInventory({
  fetchImpl = globalThis.fetch,
  storage = globalThis.sessionStorage,
  base = ".",
} = {}) {
  try {
    const cached = storage?.getItem(KEY);
    if (cached) return hydrateBundle(JSON.parse(cached));
  } catch {
    /* private mode and full quotas keep working from the network copy */
  }
  let payload = null;
  const bundleResponse = await fetchImpl(`${base}/bundle.min.json`, {
    cache: "no-cache",
  });
  if (bundleResponse?.ok) payload = await bundleResponse.json();
  if (!payload) {
    const full = await fetchImpl(`${base}/activities.json`, { cache: "no-cache" });
    if (!full?.ok) throw Error("Data unavailable");
    payload = await full.json();
  }
  try {
    storage?.setItem(KEY, JSON.stringify(payload));
  } catch {
    /* the page still has the payload for this view */
  }
  return hydrateBundle(payload);
}
