const KEY = "kc-activity-bundle-v1";

function ageLabel(ages = {}) {
  if (ages.label) return ages.label;
  if (ages.all_ages) return "All ages";
  if (ages.min == null && ages.max == null) return "Age not specified";
  if (ages.min != null && ages.max != null) return `Ages ${ages.min}–${ages.max}`;
  if (ages.min != null) return `Ages ${ages.min}+`;
  return `Ages up to ${ages.max}`;
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
  const activities = bundle.occurrences.map((occ) => {
    const offer = bundle.offerings?.[occ[0]] || {};
    const date = occ[1] || null;
    const endDate = occ[2] || date;
    const start = occ[3] || null;
    const kind = offer.schedule?.kind || "one_off";
    const ranged = kind !== "one_off";
    return hydrateRow({
      ...offer,
      id: `${offer.offering_id || occ[0]}:${date || "undated"}`,
      date,
      end_date: endDate,
      start,
      end: null,
      status: occ[4] || "scheduled",
      all_day: !start,
      stale: Boolean(occ[5]),
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
