export default function MetricsBar({ metricas }) {
  if (!metricas) return <div className="card">Cargando métricas…</div>;
  return (
    <div className="card">
      <h3>Impacto del escenario</h3>
      <div className="metric">
        <span>{metricas.poblacion_desatendida?.toLocaleString() ?? "—"}</span>
        <small>personas sin acceso oportuno (&gt;120 min)</small>
      </div>
      <div className="metric">
        <span>{metricas.tiempo_medio_min ?? "—"} min</span>
        <small>tiempo medio de acceso al hospital</small>
      </div>
      <div className="metric">
        <span>{metricas.ccpp_aislados ?? "—"}</span>
        <small>centros poblados sin ruta</small>
      </div>
    </div>
  );
}
