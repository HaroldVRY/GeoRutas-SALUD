import { useEffect, useRef, useState } from "react";
import MapView from "./components/MapView.jsx";
import ScenarioToggle from "./components/ScenarioToggle.jsx";
import MetricsBar from "./components/MetricsBar.jsx";
import TramoRanking from "./components/TramoRanking.jsx";
import { api } from "./api.js";

export default function App() {
  const [escenario, setEscenario] = useState("seco");
  const [ccpp, setCcpp] = useState(null);
  const [metricas, setMetricas] = useState(null);
  const [ranking, setRanking] = useState([]);
  const [tramos, setTramos] = useState(null);
  const [hospitales, setHospitales] = useState(null);
  const [rutas, setRutas] = useState(null);
  const [mostrarRutas, setMostrarRutas] = useState(false);
  const [loading, setLoading] = useState(true);
  const [slowNetwork, setSlowNetwork] = useState(false);
  const [error, setError] = useState(null);
  const initialLoaded = useRef(false);

  // Carga inicial: todos los endpoints a la vez (cold-start de Render puede tardar ~50 s)
  useEffect(() => {
    const slowTimer = setTimeout(() => setSlowNetwork(true), 3500);

    Promise.all([
      api.centrosPoblados("seco"),
      api.metricas("seco"),
      api.rankingTramos(20),
      api.geometriasTramos(),
      api.hospitales(),
      api.rutas("seco"),
    ])
      .then(([ccppData, metricasData, rankingData, tramosData, hospitalesData, rutasData]) => {
        clearTimeout(slowTimer);
        setCcpp(ccppData);
        setMetricas(metricasData);
        setRanking(rankingData);
        setTramos(tramosData);
        setHospitales(hospitalesData);
        setRutas(rutasData);
        initialLoaded.current = true;
        setLoading(false);
      })
      .catch((err) => {
        clearTimeout(slowTimer);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // Cambio de escenario: recarga solo ccpp + metricas (tramos no cambian)
  useEffect(() => {
    if (!initialLoaded.current) return;
    Promise.all([
      api.centrosPoblados(escenario),
      api.metricas(escenario),
      api.rutas(escenario),
    ])
      .then(([ccppData, metricasData, rutasData]) => {
        setCcpp(ccppData);
        setMetricas(metricasData);
        setRutas(rutasData);
      })
      .catch(console.error);
  }, [escenario]);

  if (loading) {
    return (
      <div className="loading-overlay">
        <div className="spinner" />
        <h2>GeoRutas SALUD</h2>
        <p>
          {slowNetwork
            ? "El servidor está despertando… puede tardar hasta 50 s en la primera visita"
            : "Cargando datos de Huancavelica…"}
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="loading-overlay">
        <h2>Error al conectar</h2>
        <p>{error}</p>
        <button
          onClick={() => window.location.reload()}
          style={{ marginTop: 14, padding: "8px 22px", borderRadius: 6, cursor: "pointer", border: "none", fontWeight: 600 }}
        >
          Reintentar
        </button>
      </div>
    );
  }

  return (
    <div className="layout">
      <header className="topbar">
        <h1>GeoRutas SALUD</h1>
        <span className="tag">Acceso oportuno a salud de emergencia · GEOTÓN 2026</span>
      </header>

      <aside className="sidebar">
        <ScenarioToggle escenario={escenario} onChange={setEscenario} />
        <div className="card">
          <h3>Capas del mapa</h3>
          <label className="layer-toggle">
            <input
              type="checkbox"
              checked={mostrarRutas}
              onChange={(e) => setMostrarRutas(e.target.checked)}
            />
            Rutas de acceso al hospital
          </label>
        </div>
        <MetricsBar metricas={metricas} />
        <TramoRanking ranking={ranking} />
      </aside>

      <main className="map">
        <MapView
          ccpp={ccpp}
          tramos={tramos}
          hospitales={hospitales}
          rutas={rutas}
          mostrarRutas={mostrarRutas}
          escenario={escenario}
        />
      </main>
    </div>
  );
}
