const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
  return res.json();
}

export const api = {
  centrosPoblados: (escenario) => get(`/api/accesibilidad/centros-poblados?escenario=${escenario}`),
  metricas: (escenario) => get(`/api/accesibilidad/metricas?escenario=${escenario}`),
  rankingTramos: (limite = 20) => get(`/api/tramos/ranking?limite=${limite}`),
  geometriasTramos: () => get(`/api/tramos/geometrias`),
  hospitales: () => get(`/api/salud/hospitales`),
};
