// public/js/api.js
// Todas las llamadas al proxy local van por acá.
// El browser NUNCA habla directo con api-football — siempre pasa por localhost:3000

const API = {

  // ── Helpers internos ──
  async _get(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`Error HTTP ${res.status} en ${path}`);
    const json = await res.json();
    if (!json.ok) throw new Error(json.error || 'Error desconocido del proxy');
    return json.data;
  },

  // ── Fixtures del torneo ──
  async fixtures(season) {
    const qs = season ? `?season=${season}` : '';
    return this._get(`/api/fixtures${qs}`);
  },

  // ── Fixtures de todas las competiciones ──
  async fixturesAll(season) {
    const qs = season ? `?season=${season}` : '';
    return this._get(`/api/fixtures/all${qs}`);
  },

  // ── Tabla de posiciones ──
  async standings(season) {
    const qs = season ? `?season=${season}` : '';
    const data = await this._get(`/api/standings${qs}`);
    // api-football devuelve standings[0].league.standings[0] (array de grupos/zonas)
    return data?.[0]?.league?.standings?.[0] ?? [];
  },

  // ── Estadísticas del equipo ──
  async statistics(season) {
    const qs = season ? `?season=${season}` : '';
    return this._get(`/api/statistics${qs}`);
  },

  // ── Plantel ──
  async players(season, page = 1) {
    const qs = new URLSearchParams({ ...(season ? { season } : {}), page }).toString();
    return this._get(`/api/players?${qs}`);
  },

  // ── Detalle de un partido ──
  async fixture(id) {
    return this._get(`/api/fixture/${id}`);
  },

  // ── Eventos (goles, tarjetas) de un partido ──
  async fixtureEvents(id) {
    return this._get(`/api/fixture/${id}/events`);
  },

  // ── Estado de la API (cuota disponible) ──
  async status() {
    return this._get('/api/status');
  },
};

// ── Helpers de transformación ──
// Convierte un fixture de api-football al formato que usa el sitio

function transformarFixture(f) {
  const home = f.teams.home;
  const away = f.teams.away;
  const esLocal = home.id === parseInt(document.body.dataset.teamId || 435);

  return {
    id:           f.fixture.id,
    fecha:        f.fixture.date.split('T')[0],
    hora:         f.fixture.date.split('T')[1]?.slice(0, 5) ?? null,
    rival:        esLocal ? away.name  : home.name,
    rivalLogo:    esLocal ? away.logo  : home.logo,
    condicion:    esLocal ? 'local'    : 'visita',
    estadio:      f.fixture.venue?.name ?? null,
    ciudad:       f.fixture.venue?.city ?? null,
    competicion:  f.league.name,
    competicionId:f.league.id,
    ronda:        f.league.round,
    estado:       f.fixture.status.short,   // FT, NS, 1H, 2H, HT, etc.
    estadoTexto:  f.fixture.status.long,
    golesFavor:   esLocal ? f.goals.home : f.goals.away,
    golesContra:  esLocal ? f.goals.away : f.goals.home,
    resultado: (() => {
      const gf = esLocal ? f.goals.home : f.goals.away;
      const gc = esLocal ? f.goals.away : f.goals.home;
      if (gf === null || gc === null) return null;
      return gf > gc ? 'G' : gf === gc ? 'E' : 'P';
    })(),
  };
}

function transformarStanding(s) {
  return {
    posicion:   s.rank,
    equipo:     s.team.name,
    equipoId:   s.team.id,
    logo:       s.team.logo,
    pj:         s.all.played,
    pts:        s.points,
    gf:         s.all.goals.for,
    gc:         s.all.goals.against,
    dg:         s.goalsDiff,
    forma:      s.form, // "WDLWW"
  };
}

// Exportar para uso en otras páginas
window.API = API;
window.transformarFixture  = transformarFixture;
window.transformarStanding = transformarStanding;
