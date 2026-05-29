import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, GeoJSON, useMap } from "react-leaflet";
import L from "leaflet";

const CENTRO_HUANCAVELICA = [-12.85, -74.9];
const ZOOM_INICIAL = 8;

const hospitalIcon = L.divIcon({
  className: "",
  html: '<div style="width:20px;height:20px;background:#0b5394;border:2.5px solid #fff;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:14px;line-height:1;box-shadow:0 1px 5px rgba(0,0,0,0.5)">+</div>',
  iconSize: [20, 20],
  iconAnchor: [10, 10],
  popupAnchor: [0, -12],
});

// Rutas de acceso: gris-azulado tenue (contexto, no la recomendación)
const ESTILO_RUTA    = { color: "#5b7a99", weight: 1.2, opacity: 0.5 };
const ESTILO_TOP1    = { color: "#c0392b", weight: 7,   opacity: 0.92 };
const ESTILO_OTROS   = { color: "#2980b9", weight: 2.5, opacity: 0.6 };

// --- Leyenda ---
function dot(color, borderColor) {
  const border = borderColor ? `border:2.5px solid ${borderColor};` : "";
  return `<span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:${color};${border}box-shadow:0 1px 3px rgba(0,0,0,0.2);flex-shrink:0"></span>`;
}
function hospitalDot() {
  return `<span style="display:inline-flex;width:16px;height:16px;background:#0b5394;border:2px solid #fff;border-radius:50%;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:11px;box-shadow:0 1px 3px rgba(0,0,0,0.35);flex-shrink:0;line-height:1">+</span>`;
}
function lineSymbol(color, heightPx, opacity) {
  return `<span style="display:inline-block;width:22px;height:${heightPx}px;background:${color};opacity:${opacity};border-radius:2px;flex-shrink:0"></span>`;
}
function legendItem(symbol, text) {
  return `<div style="display:flex;align-items:center;gap:8px;margin:4px 0">${symbol}<span style="font-size:12px">${text}</span></div>`;
}
function buildLegendHTML(mostrarRutas, escenario) {
  let html = `<div style="font-weight:700;color:#0b5394;margin-bottom:7px;font-size:13px">Leyenda</div>`;
  html += legendItem(dot("#1a8a5a"), "CCPP con acceso (≤120 min)");
  html += legendItem(dot("#b03a3a"), "CCPP en brecha (&gt;120 min)");
  if (escenario === "lluvias") {
    html += legendItem(dot("#b03a3a", "#e67e22"), "Pierde acceso en lluvias");
  }
  html += legendItem(hospitalDot(), "Hospital resolutivo");
  html += `<div style="margin:6px 0 3px;border-top:1px solid #e8edf2;padding-top:5px">`;
  html += legendItem(lineSymbol("#c0392b", 4, 1), "Corredor top 1 (prioridad)");
  html += legendItem(lineSymbol("#2980b9", 2, 0.9), "Corredor de inversión");
  html += `</div>`;
  if (mostrarRutas) {
    html += legendItem(lineSymbol("#5b7a99", 2, 0.65), "Ruta de acceso al hospital");
  }
  return html;
}

function MapLegend({ mostrarRutas, escenario }) {
  const map = useMap();
  useEffect(() => {
    const legend = L.control({ position: "bottomleft" });
    legend.onAdd = () => {
      const div = L.DomUtil.create("div", "map-legend");
      div.innerHTML = buildLegendHTML(mostrarRutas, escenario);
      return div;
    };
    legend.addTo(map);
    return () => legend.remove();
  }, [map, mostrarRutas, escenario]);
  return null;
}

export default function MapView({ ccpp, tramos, hospitales, rutas, mostrarRutas, escenario, nuevosBrechaLluvias, top1TramoId }) {
  // Dividir corredores: top 1 se renderiza en capa propia DESPUÉS de los demás
  // → z-order garantizado: top 1 siempre encima de los otros corredores
  const tramosOtros = useMemo(() => {
    if (!tramos?.features) return null;
    const features = tramos.features.filter(
      (f) => String(f.properties?.tramo_id) !== top1TramoId
    );
    return features.length ? { ...tramos, features } : null;
  }, [tramos, top1TramoId]);

  const tramoTop1 = useMemo(() => {
    if (!tramos?.features || !top1TramoId) return null;
    const features = tramos.features.filter(
      (f) => String(f.properties?.tramo_id) === top1TramoId
    );
    return features.length ? { ...tramos, features } : null;
  }, [tramos, top1TramoId]);

  // Estilo de CCPP: resalta con borde ámbar los que pierden acceso al pasar a lluvias
  const getCcppStyle = useMemo(() => {
    return (feature) => {
      const enBrecha = feature?.properties?.en_brecha;
      const nombre = feature?.properties?.nombre ?? "";
      const [lon, lat] = feature?.geometry?.coordinates ?? [0, 0];
      const key = `${nombre}|${lon.toFixed(5)}|${lat.toFixed(5)}`;
      if (nuevosBrechaLluvias?.has(key)) {
        return { radius: 5, color: "#e67e22", fillColor: "#b03a3a", fillOpacity: 0.88, weight: 3 };
      }
      return {
        radius: 5,
        color: enBrecha ? "#b03a3a" : "#1a8a5a",
        fillColor: enBrecha ? "#b03a3a" : "#1a8a5a",
        fillOpacity: 0.78,
        weight: 1,
      };
    };
  }, [nuevosBrechaLluvias]);

  return (
    <MapContainer
      center={CENTRO_HUANCAVELICA}
      zoom={ZOOM_INICIAL}
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <MapLegend mostrarRutas={mostrarRutas} escenario={escenario} />

      {/* 1a. Corredores de inversión (todos menos top 1) — capa base */}
      {tramosOtros && (
        <GeoJSON
          key="tramos-otros"
          data={tramosOtros}
          style={() => ESTILO_OTROS}
          onEachFeature={(f, layer) => {
            const p = f.properties || {};
            layer.bindPopup(
              `<b>${p.nombre ?? "Corredor"}</b><br/>${p.longitud_km ?? "?"} km · score ${Math.round(p.score ?? 0).toLocaleString()}`
            );
          }}
        />
      )}

      {/* 1b. Corredor top 1 — siempre encima de los demás corredores */}
      {tramoTop1 && (
        <GeoJSON
          key="tramos-top1"
          data={tramoTop1}
          style={() => ESTILO_TOP1}
          onEachFeature={(f, layer) => {
            const p = f.properties || {};
            layer.bindPopup(
              `<b>${p.nombre ?? "Corredor"}</b> <span style='color:#c0392b'>★ Top 1</span><br/>${p.longitud_km ?? "?"} km · score ${Math.round(p.score ?? 0).toLocaleString()}`
            );
          }}
        />
      )}

      {/* 2. Rutas de acceso (gris-azulado tenue, contexto) */}
      {mostrarRutas && rutas && (
        <GeoJSON
          key={"rutas-" + escenario}
          data={rutas}
          style={() => ESTILO_RUTA}
          onEachFeature={(f, layer) => {
            const p = f.properties || {};
            layer.bindPopup(
              `<b>${p.ccpp ?? "CCPP"}</b><br/>${p.minutos ?? "?"} min → ${p.hospital_destino ?? "Hospital"}`
            );
          }}
        />
      )}

      {/* 3. Centros poblados */}
      {ccpp && (
        <GeoJSON
          key={escenario}
          data={ccpp}
          pointToLayer={(f, latlng) => L.circleMarker(latlng, getCcppStyle(f))}
          onEachFeature={(f, layer) => {
            const p = f.properties || {};
            const [lon, lat] = f.geometry?.coordinates ?? [0, 0];
            const key = `${p.nombre ?? ""}|${lon.toFixed(5)}|${lat.toFixed(5)}`;
            const esNuevo = nuevosBrechaLluvias?.has(key);
            const mins = p.minutos != null ? Math.round(p.minutos) : "?";
            let brechaTag = "";
            if (esNuevo) {
              brechaTag = "<br/><span style='color:#e67e22;font-weight:600'>⚠ Pierde acceso en lluvias</span>";
            } else if (p.en_brecha) {
              brechaTag = "<br/><span style='color:#b03a3a;font-weight:600'>En brecha (&gt;120 min)</span>";
            }
            layer.bindPopup(`<b>${p.nombre ?? "CCPP"}</b><br/>Acceso: ${mins} min${brechaTag}`);
          }}
        />
      )}

      {/* 4. Hospitales resolutivos — encima de todo */}
      {hospitales && (
        <GeoJSON
          key="hospitales"
          data={hospitales}
          pointToLayer={(f, latlng) => L.marker(latlng, { icon: hospitalIcon })}
          onEachFeature={(f, layer) => {
            const p = f.properties || {};
            layer.bindPopup(
              `<b>${p.nombre ?? "Hospital"}</b><br/>Categoría: ${p.categoria ?? "—"}`
            );
          }}
        />
      )}
    </MapContainer>
  );
}
