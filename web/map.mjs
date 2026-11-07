import { mapGroups } from "./map-data.mjs";
import { activityHref, scheduleLabel } from "./activity-view.mjs";

let leafletPromise, clusterPromise;
function leaflet() {
  if (globalThis.L) return Promise.resolve(globalThis.L);
  if (!leafletPromise)
    leafletPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "./vendor/leaflet/leaflet.js";
      s.onload = () => resolve(globalThis.L);
      s.onerror = () => {
        leafletPromise = null;
        reject(Error("Map library could not be loaded"));
      };
      document.head.append(s);
    });
  return leafletPromise;
}
async function clusteredLeaflet() {
  const L = await leaflet();
  if (L.markerClusterGroup) return L;
  clusterPromise ||= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "./vendor/leaflet-markercluster/leaflet.markercluster.js";
    script.onload = () => resolve(L);
    script.onerror = () => {
      clusterPromise = null;
      reject(Error("Map clustering could not be loaded"));
    };
    document.head.append(script);
  });
  return clusterPromise;
}
function el(tag, value, cls) {
  const e = document.createElement(tag);
  e.textContent = value;
  if (cls) e.className = cls;
  return e;
}
export class ActivityMap {
  constructor(container, status) {
    this.container = container;
    this.status = status;
    this.signature = "";
    this.markers = new Map();
  }
  async init() {
    if (this.initialization) return this.initialization;
    this.initialization = this.initialize().catch((error) => {
      this.initialization = null;
      throw error;
    });
    return this.initialization;
  }
  async initialize() {
    const L = await clusteredLeaflet();
    const response = await fetch("./map-config.json");
    if (!response.ok) throw Error("Map settings unavailable");
    const config = await response.json();
    if (!config.tile_url.startsWith("https://"))
      throw Error("Invalid tile endpoint");
    this.L = L;
    this.map = L.map(this.container, {
      scrollWheelZoom: false,
      minZoom: 5,
      maxZoom: 18,
    }).setView([38.6, -94.2], 7);
    L.tileLayer(config.tile_url, {
      attribution: config.attribution,
      maxZoom: 18,
    })
      .on("tileerror", () => {
        this.status.textContent =
          "Basemap temporarily unavailable; activity pins and the list still work.";
      })
      .addTo(this.map);
    this.layer = L.markerClusterGroup({
      maxClusterRadius: 45,
      disableClusteringAtZoom: 16,
      showCoverageOnHover: false,
      iconCreateFunction: (cluster) => {
        const ids = new Set(
          cluster.getAllChildMarkers().flatMap((m) => m.options.offeringIds),
        );
        return L.divIcon({
          className: "activity-cluster",
          html: `<span>${ids.size}</span>`,
          iconSize: [44, 44],
          iconAnchor: [22, 22],
        });
      },
    }).addTo(this.map);
    L.control.scale({ imperial: true, metric: true }).addTo(this.map);
  }
  async update(rows, places, { preserveView = false, focus = null } = {}) {
    const revision = (this.revision = (this.revision || 0) + 1);
    await this.init();
    if (revision !== this.revision) return;
    const groups = mapGroups(rows),
      L = this.L;
    this.layer.clearLayers();
    this.markers.clear();
    for (const g of groups) {
      const place = places.find((p) => p.id === g.records[0].place_id);
      const name = place?.name || g.records[0].venue;
      const marker = L.marker([g.lat, g.lng], {
        title: name + ": " + g.offerings.length + " activities",
        keyboard: true,
        offeringIds: g.offerings.map((a) => a.offering_id || a.id),
        icon: L.divIcon({
          className: "activity-pin",
          html: `<span>${g.offerings.length}</span>`,
          iconSize: [34, 34],
          iconAnchor: [17, 17],
        }),
      });
      const popup = el("div", "", "map-popup");
      popup.append(
        el("h3", name),
        el(
          "p",
          g.offerings.length +
            " distinct activities · " +
            g.records.length +
            " published records",
          "map-popup-count",
        ),
      );
      popup.append(el("p", g.records[0].geo.note, "map-precision"));
      const list = el("ul", "");
      for (const a of g.offerings) {
        const li = el("li", ""),
          link = el("a", a.title);
        link.href = activityHref(a);
        li.append(link, el("small", scheduleLabel(a)));
        list.append(li);
        this.markers.set(a.offering_id || a.id, marker);
      }
      popup.append(list);
      marker.bindPopup(popup, { maxWidth: 320, maxHeight: 330 });
      this.layer.addLayer(marker);
    }
    const signature = groups
      .map((g) => g.key)
      .sort()
      .join("|");
    if (groups.length && signature !== this.signature && !preserveView)
      this.map.fitBounds(L.latLngBounds(groups.map((g) => [g.lat, g.lng])), {
        padding: [35, 35],
        maxZoom: 13,
      });
    this.signature = signature;
    this.map.invalidateSize();
    if (focus) this.focus(focus);
  }
  focus(id) {
    const m = this.markers.get(id);
    if (m) {
      this.map.setView(m.getLatLng(), Math.max(this.map.getZoom(), 12));
      this.layer.zoomToShowLayer(m, () => m.openPopup());
    }
  }
  bounds() {
    if (!this.map) return null;
    const b = this.map.getBounds();
    return {
      south: b.getSouth(),
      north: b.getNorth(),
      west: b.getWest(),
      east: b.getEast(),
    };
  }
  fit() {
    this.signature = "";
  }
}
