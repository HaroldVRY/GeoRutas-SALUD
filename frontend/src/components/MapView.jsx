import { useMemo } from "react";
import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import L from "leaflet";

const CENTRO_HUANCAVELICA = [-12.85, -74.9];
const ZOOM_INICIAL = 8;

// Ícono de hospital: círculo azul con "+" blanco
const hospitalIcon = L.divIcon({
  className: "",
  html: '<div style="width:20px;height:20px;background:#0b5394;border:2.5px solid #fff;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:14px;line-height:1;box-shadow:0 1px 5px rgba(0,0,0,0.5)">+</div>',
  iconSize: [20, 20],
  iconAnchor: [10, 10],
  popupAnchor: [0, -12],
});

function estiloCcpp(feature) {
  const enBrecha = feature?.properties?.en_brecha;
  return {
    radius: 5,
    color: enBrecha ? "#b03a3a" : "#1a8a5a",
    fillColor: enBrecha ? "#b03a3a" : "#1a8a5a",
    fillOpacity: 0.78,
    weight: 1,
  };
}

const estiloRuta = { color: "#e67e22", weight: 1.5, opacity: 0.75 };

export default function MapView({ ccpp, tramos, hospitales, rutas, mostrarRutas, escenario }) {
  // Top 1 (primer feature, ordenado por score desc): rojo grueso prominente.
  // Resto: azul más fino pero visible.
  const estiloTramoFn = useMemo(() => {
    if (!tramos?.features?.length) return () => ({ color: "#2980b9", weight: 2.5, opacity: 0.6 });
    const top1Id = String(tramos.features[0].properties?.tramo_id);
    return (feature) => {
      const isTop1 = String(feature?.properties?.tramo_id) === top1Id;
      return isTop1
        ? { color: "#c0392b", weight: 7, opacity: 0.92 }
        : { color: "#2980b9", weight: 2.5, opacity: 0.6 };
    };
  }, [tramos]);

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

      {/* 1. Corredores de inversión (líneas) — base del análisis */}
      {tramos && (
        <GeoJSON
          key="tramos"
          data={tramos}
          style={estiloTramoFn}
          onEachFeature={(f, layer) => {
            const p = f.properties || {};
            const esTop1 = tramos.features[0]?.properties?.tramo_id === p.tramo_id;
            layer.bindPopup(
              `<b>${p.nombre ?? "Corredor"}</b>${esTop1 ? " <span style='color:#c0392b'>★ Top 1</span>" : ""}<br/>${p.longitud_km ?? "?"} km · score ${Math.round(p.score ?? 0).toLocaleString()}`
            );
          }}
        />
      )}

      {/* 2. Rutas de acceso al hospital (naranja, ocultas por defecto) */}
      {mostrarRutas && rutas && (
        <GeoJSON
          key={"rutas-" + escenario}
          data={rutas}
          style={estiloRuta}
          onEachFeature={(f, layer) => {
            const p = f.properties || {};
            layer.bindPopup(
              `<b>${p.ccpp ?? "CCPP"}</b><br/>${p.minutos ?? "?"} min → ${p.hospital_destino ?? "Hospital"}`
            );
          }}
        />
      )}

      {/* 3. Centros poblados — rojo = en brecha, verde = con acceso */}
      {ccpp && (
        <GeoJSON
          key={escenario}
          data={ccpp}
          pointToLayer={(f, latlng) => L.circleMarker(latlng, estiloCcpp(f))}
          onEachFeature={(f, layer) => {
            const p = f.properties || {};
            const mins = p.minutos != null ? Math.round(p.minutos) : "?";
            const brecha = p.en_brecha
              ? "<br/><span style='color:#b03a3a;font-weight:600'>En brecha (&gt;120 min)</span>"
              : "";
            layer.bindPopup(`<b>${p.nombre ?? "CCPP"}</b><br/>Acceso: ${mins} min${brecha}`);
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
