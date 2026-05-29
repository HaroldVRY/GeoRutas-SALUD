export default function ScenarioToggle({ escenario, onChange }) {
  return (
    <div className="card">
      <h3>Escenario</h3>
      <div className="toggle">
        <button
          className={escenario === "seco" ? "active" : ""}
          onClick={() => onChange("seco")}
        >
          Seco
        </button>
        <button
          className={escenario === "lluvias" ? "active" : ""}
          onClick={() => onChange("lluvias")}
        >
          Lluvias
        </button>
      </div>
    </div>
  );
}
