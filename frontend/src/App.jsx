import { useEffect, useMemo, useState } from "react";
import MapView from "./components/MapView.jsx";
import ScenarioToggle from "./components/ScenarioToggle.jsx";
import MetricsBar from "./components/MetricsBar.jsx";
import TramoRanking from "./components/TramoRanking.jsx";
import { api } from "./api.js";

export default function App() {
  const [escenario, setEscenario] = useState("seco");
  // Ambos escenarios cargados al inicio: { seco: {ccpp, metricas, rutas}, lluvias: {...} }
  // El toggle solo selecciona cuál mostrar — cero re-fetch, cero condición de carrera.
  const [allData, setAllData] = useState(null);
  const [ranking, setRanking] = useState([]);
  const [tramos, setTramos] = useState(null);
  const [hospitales, setHospitales] = useState(null);
  const [mostrarRutas, setMostrarRutas] = useState(false);
  const [loading, setLoading] = useState(true);
  const [slowNetwork, setSlowNetwork] = useState(false);
  const [error, setError] = useState(null);

  // Carga inicial: todos los endpoints de ambos escenarios en paralelo
  useEffect(() => {
    const slowTimer = setTimeout(() => setSlowNetwork(true), 3500);
    Promise.all([
      api.centrosPoblados("seco"),
      api.metricas("seco"),
      api.rutas("seco"),
      api.centrosPoblados("lluvias"),
      api.metricas("lluvias"),
      api.rutas("lluvias"),
      api.rankingTramos(20),
      api.geometriasTramos(),
      api.hospitales(),
    ])
      .then(([ccppSeco, metricasSeco, rutasSeco, ccppLluv, metricasLluv, rutasLluv, rankingData, tramosData, hospitalesData]) => {
        clearTimeout(slowTimer);
        setAllData({
          seco:    { ccpp: ccppSeco,    metricas: metricasSeco,    rutas: rutasSeco    },
          lluvias: { ccpp: ccppLluv,    metricas: metricasLluv,    rutas: rutasLluv    },
        });
        setRanking(rankingData);
        setTramos(tramosData);
        setHospitales(hospitalesData);
        setLoading(false);
      })
      .catch((err) => {
        clearTimeout(slowTimer);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // Datos del escenario activo — derivados de allData, sin async
  const ccpp     = allData?.[escenario]?.ccpp     ?? null;
  const metricas = allData?.[escenario]?.metricas ?? null;
  const rutas    = allData?.[escenario]?.rutas    ?? null;

  // CCPP que pierden acceso al pasar a lluvias.
  // Clave compuesta nombre|lon|lat evita colisiones entre CCPP homónimos.
  // allData es estable (se asigna una sola vez) — solo recomputa al cambiar escenario.
  const nuevosBrechaLluvias = useMemo(() => {
    if (escenario !== "lluvias") return new Set();
    const secoData = allData?.seco?.ccpp;
    const lluvData = allData?.lluvias?.ccpp;
    if (!secoData || !lluvData) return new Set();
    const makeKey = (f) => {
      const [lon, lat] = f.geometry.coordinates;
      return `${f.properties.nombre}|${lon.toFixed(5)}|${lat.toFixed(5)}`;
    };
    const secoConAcceso = new Set(
      secoData.features.filter((f) => !f.properties.en_brecha).map(makeKey)
    );
    return new Set(
      lluvData.features
        .filter((f) => f.properties.en_brecha && secoConAcceso.has(makeKey(f)))
        .map(makeKey)
    );
  }, [escenario, allData]);

  // ID del corredor top 1 según el ranking (fuente de verdad), no según orden del GeoJSON
  const top1TramoId = String(ranking[0]?.tramo_id ?? "");

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
          nuevosBrechaLluvias={nuevosBrechaLluvias}
          top1TramoId={top1TramoId}
        />
      </main>
    </div>
  );
}
