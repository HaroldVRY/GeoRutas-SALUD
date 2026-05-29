export default function MetricsBar({ metricas }) {
  if (!metricas) return <div className="card">Cargando métricas…</div>;
  return (
    <div className="card">
      <h3>Impacto</h3>
      <div className="metric">
        <span>{metricas.poblacion_desatendida ?? "—"}</span>
        <small>población desatendida</small>
      </div>
      <div className="metric">
        <span>{metricas.tiempo_medio_min ?? "—"} min</span>
        <small>tiempo medio de acceso</small>
      </div>
      <div className="metric">
        <span>{metricas.ccpp_aislados ?? "—"}</span>
        <small>centros poblados aislados</small>
      </div>
    </div>
  );
}
