export default function TramoRanking({ ranking }) {
  return (
    <div className="card">
      <h3>Tramos a priorizar</h3>
      <ol className="ranking">
        {ranking.length === 0 && <li>Sin datos aún</li>}
        {ranking.map((t, i) => (
          <li key={t.tramo_id ?? i}>
            <b>{t.nombre ?? `Tramo ${i + 1}`}</b>
            <small>{t.region} · benef. {t.pob_beneficiada ?? "—"}</small>
          </li>
        ))}
      </ol>
    </div>
  );
}
