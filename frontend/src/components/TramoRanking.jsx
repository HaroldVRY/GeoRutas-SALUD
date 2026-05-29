export default function TramoRanking({ ranking }) {
  return (
    <div className="card">
      <h3>Tramos a priorizar</h3>
      <ol className="ranking">
        {ranking.length === 0 && <li>Sin datos aún</li>}
        {ranking.map((t, i) => (
          <li key={t.tramo_id ?? i} className={i === 0 ? "top1" : ""}>
            <b>{t.nombre ?? `Corredor ${i + 1}`}</b>
            <small>
              {t.longitud_km != null ? `${t.longitud_km} km` : ""}
              {t.score != null
                ? ` · ${Math.round(t.score).toLocaleString()} min·vuln ahorrados`
                : ""}
            </small>
            <small className="region">{t.region}</small>
          </li>
        ))}
      </ol>
    </div>
  );
}
