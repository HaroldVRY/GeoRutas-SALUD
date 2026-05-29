import { useEffect, useState } from "react";
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

  useEffect(() => {
    api.centrosPoblados(escenario).then(setCcpp).catch(console.error);
    api.metricas(escenario).then(setMetricas).catch(console.error);
  }, [escenario]);

  useEffect(() => {
    api.rankingTramos(20).then(setRanking).catch(console.error);
  }, []);

  return (
    <div className="layout">
      <header className="topbar">
        <h1>GeoRutas SALUD</h1>
        <span className="tag">Acceso oportuno a salud de emergencia · GEOTÓN 2026</span>
      </header>

      <aside className="sidebar">
        <ScenarioToggle escenario={escenario} onChange={setEscenario} />
        <MetricsBar metricas={metricas} />
        <TramoRanking ranking={ranking} />
      </aside>

      <main className="map">
        <MapView ccpp={ccpp} />
      </main>
    </div>
  );
}
