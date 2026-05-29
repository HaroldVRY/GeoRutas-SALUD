import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import L from "leaflet";

// Centro aproximado del Perú
const CENTRO = [-9.19, -75.0];

function estiloCcpp(feature) {
  const enBrecha = feature?.properties?.en_brecha;
  return {
    radius: 5,
    color: enBrecha ? "#b03a3a" : "#1a8a5a",
    fillColor: enBrecha ? "#b03a3a" : "#1a8a5a",
    fillOpacity: 0.7,
    weight: 1,
  };
}

export default function MapView({ ccpp }) {
  return (
    <MapContainer center={CENTRO} zoom={6} style={{ height: "100%", width: "100%" }}>
      <TileLayer
        attribution='&copy; OpenStreetMap'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {ccpp && (
        <GeoJSON
          key={JSON.stringify(ccpp).length}
          data={ccpp}
          pointToLayer={(f, latlng) => L.circleMarker(latlng, estiloCcpp(f))}
          onEachFeature={(f, layer) => {
            const p = f.properties || {};
            layer.bindPopup(
              `<b>${p.nombre ?? "CCPP"}</b><br/>Acceso: ${p.minutos ?? "?"} min`
            );
          }}
        />
      )}
    </MapContainer>
  );
}
