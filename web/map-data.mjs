export function hasCoordinates(a) {
  const g = a.geo;
  return (
    !!g &&
    Number.isFinite(g.lat) &&
    Number.isFinite(g.lng) &&
    Math.abs(g.lat) <= 90 &&
    Math.abs(g.lng) <= 180
  );
}
export function withinBounds(a, b) {
  return (
    hasCoordinates(a) &&
    a.geo.lat >= b.south &&
    a.geo.lat <= b.north &&
    a.geo.lng >= b.west &&
    a.geo.lng <= b.east
  );
}
export function mapGroups(rows) {
  const groups = new Map();
  for (const a of rows) {
    if (!hasCoordinates(a)) continue;
    const key = a.geo.lat.toFixed(5) + "," + a.geo.lng.toFixed(5);
    if (!groups.has(key))
      groups.set(key, {
        key,
        lat: a.geo.lat,
        lng: a.geo.lng,
        records: [],
        offerings: new Map(),
      });
    const g = groups.get(key);
    g.records.push(a);
    if (!g.offerings.has(a.offering_id || a.id))
      g.offerings.set(a.offering_id || a.id, a);
  }
  return [...groups.values()].map((g) => ({
    ...g,
    offerings: [...g.offerings.values()],
  }));
}
