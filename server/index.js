// server/index.js
// Servidor ultra-simple: sirve los archivos estáticos de /public
// Los JSONs ya los generó el scraper de Python — este no llama a ninguna API externa

require('dotenv').config();
const express = require('express');
const path    = require('path');
const fs      = require('fs');

const app  = express();
const PORT = process.env.PORT || 3000;

// ── Helpers ──
function leerJSON(nombre) {
  const p = path.join(__dirname, '../public/data', `${nombre}.json`);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

// ════════════════════════════════════════════════
//  API LOCAL (lee los JSONs que generó Python)
// ════════════════════════════════════════════════

// GET /api/partidos?season=2026
// Lee siempre partidos.json y filtra por año si se pide
app.get('/api/partidos', (req, res) => {
  const todos = leerJSON('partidos');
  if (!todos) return res.status(404).json({ ok: false, error: 'Sin datos de partidos. Corré python scraper/fotmob.py' });

  const season = req.query.season ? parseInt(req.query.season) : null;
  const data = season
    ? todos.filter(p => p.fecha && p.fecha.startsWith(String(season)))
    : todos;

  res.json({ ok: true, data });
});

// GET /api/standings
app.get('/api/standings', (req, res) => {
  const data = leerJSON('standings');
  if (!data) return res.status(404).json({ ok: false, error: 'Sin datos de standings' });
  res.json({ ok: true, data });
});

// GET /api/plantel
app.get('/api/plantel', (req, res) => {
  const data = leerJSON('plantel');
  if (!data) return res.status(404).json({ ok: false, error: 'Sin datos de plantel' });
  res.json({ ok: true, data });
});

// GET /api/seasons  — extrae las temporadas disponibles desde partidos.json
app.get('/api/seasons', (req, res) => {
  const todos = leerJSON('partidos');
  if (!todos || !todos.length) return res.json({ ok: true, data: [] });

  const years = [...new Set(
    todos
      .filter(p => p.fecha)
      .map(p => parseInt(p.fecha.substring(0, 4)))
      .filter(y => !isNaN(y))
  )].sort((a, b) => b - a);

  res.json({ ok: true, data: years });
});

// GET /api/liga  — tabla completa + fixture fecha + tops
app.get('/api/liga', (req, res) => {
  const data = leerJSON('liga');
  if (!data) return res.status(404).json({ ok: false, error: 'Sin datos de liga. Corré python scraper/fotmob.py' });
  res.json({ ok: true, data });
});

// GET /api/meta  — info de última actualización
app.get('/api/meta', (req, res) => {
  const data = leerJSON('meta');
  res.json({ ok: true, data: data || { ultima_actualizacion: null } });
});

// GET /api/detalles/:season/:matchId
app.get('/api/detalles/:season/:matchId', (req, res) => {
  const data = leerJSON(`detalles_${req.params.season}`);
  if (!data) return res.status(404).json({ ok: false, error: 'Sin detalles' });
  const detalle = data[req.params.matchId];
  if (!detalle) return res.status(404).json({ ok: false, error: 'Partido no encontrado' });
  res.json({ ok: true, data: detalle });
});

// ── Archivos estáticos ──
app.use(express.static(path.join(__dirname, '../public')));

app.get('*', (req, res) => {
  if (!req.path.startsWith('/api')) {
    res.sendFile(path.join(__dirname, '../public/index.html'));
  }
});

// ── Arrancar ──
app.listen(PORT, () => {
  const meta   = leerJSON('meta');
  const ultima = meta?.ultima_actualizacion
    ? new Date(meta.ultima_actualizacion).toLocaleString('es-AR')
    : 'nunca (corré python scraper/fotmob.py)';

  console.log('');
  console.log('  ⚽ CAI — Servidor iniciado');
  console.log(`  → http://localhost:${PORT}`);
  console.log(`  → Última actualización: ${ultima}`);
  console.log('');
});