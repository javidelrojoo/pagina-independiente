"""
scraper/fotmob.py
=================
Scraper de FotMob para Club Atlético Independiente.

Fuentes:
  - Temporada actual:   https://www.fotmob.com/api/data/teams?id=10078&ccode3=ARG
  - Fixtures históricos: https://pub.fotmob.com/prod/db/api/team/10078/fixture-by-date?beforeTimestamp=XXXX

Uso:
    python scraper/fotmob.py              # scrape todo
    python scraper/fotmob.py --check      # verificar conectividad
    python scraper/fotmob.py --history    # también scrapear partidos históricos
    python scraper/fotmob.py --raw        # guardar JSON crudo (debug)
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ══════════════════════════════════════════════════
#  CONFIGURACIÓN
# ══════════════════════════════════════════════════

TEAM_ID   = 10078   # Club Atlético Independiente
CCODE     = "ARG"

# Endpoint principal — siempre devuelve la temporada más reciente
TEAM_URL  = f"https://www.fotmob.com/api/data/teams?id={TEAM_ID}&ccode3={CCODE}"

# Endpoint histórico — paginado por timestamp
HISTORY_URL = f"https://pub.fotmob.com/prod/db/api/team/{TEAM_ID}/fixture-by-date"

OUTPUT_DIR = Path(__file__).parent.parent / "public" / "data"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Origin":  "https://www.fotmob.com",
    "Referer": "https://www.fotmob.com/",
}

# Pausa entre requests para no sobrecargar el servidor
REQUEST_DELAY = 1.5


# ══════════════════════════════════════════════════
#  HTTP
# ══════════════════════════════════════════════════

session = requests.Session()
session.headers.update(HEADERS)


def get(url: str, params: dict = None) -> dict:
    print(f"  GET {url}" + (f" {params}" if params else ""))
    r = session.get(url, params=params, timeout=20)
    r.raise_for_status()
    time.sleep(REQUEST_DELAY)
    return r.json()


# ══════════════════════════════════════════════════
#  TRANSFORMADORES
# ══════════════════════════════════════════════════

def transformar_fixture(f: dict) -> dict | None:
    """
    Transforma un fixture del array allFixtures.fixtures.
    Estructura real confirmada del JSON pegado por el usuario.
    """
    try:
        status = f.get("status", {})
        home   = f.get("home", {})
        away   = f.get("away", {})
        tourn  = f.get("tournament", {})

        home_id  = home.get("id")
        es_local = (home_id == TEAM_ID)

        # Rival (viene también en "opponent")
        opp = f.get("opponent", {})
        rival_nombre = opp.get("name") or (away.get("name") if es_local else home.get("name"))
        rival_id     = away.get("id") if es_local else home.get("id")

        # Fecha
        utc_time = status.get("utcTime", "")
        if utc_time:
            dt    = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
            fecha = dt.strftime("%Y-%m-%d")
            hora  = dt.strftime("%H:%M")
        else:
            return None  # sin fecha no sirve

        # Estado
        finished  = status.get("finished", False)
        started   = status.get("started", False)
        cancelled = status.get("cancelled", False)
        if cancelled:
            return None
        en_curso = started and not finished

        # Marcador — home.score / away.score ya vienen orientados al partido
        gf = gc = None
        if finished or en_curso:
            h_score = home.get("score")
            a_score = away.get("score")
            if h_score is not None and a_score is not None:
                gf = int(h_score) if es_local else int(a_score)
                gc = int(a_score) if es_local else int(h_score)

        # Resultado desde perspectiva de Independiente
        resultado = None
        if finished and gf is not None and gc is not None:
            resultado = "G" if gf > gc else ("E" if gf == gc else "P")

        return {
            "id":             f.get("id"),
            "fecha":          fecha,
            "hora":           hora,
            "rival":          rival_nombre,
            "rival_id":       rival_id,
            "condicion":      "local" if es_local else "visita",
            "competicion":    tourn.get("name", "—"),
            "competicion_id": tourn.get("leagueId"),
            "terminado":      finished,
            "en_curso":       en_curso,
            "goles_favor":    gf,
            "goles_contra":   gc,
            "resultado":      resultado,
            "page_url":       f.get("pageUrl", ""),
        }
    except Exception as e:
        print(f"    ⚠ Error en fixture {f.get('id')}: {e}")
        return None


def transformar_partido_liga(f: dict) -> dict | None:
    """
    Transforma un partido de la jornada actual de la liga.
    Perspectiva neutra (no desde CAI) — muestra local vs visita completo.
    """
    try:
        status = f.get("status", {})
        home   = f.get("home", {})
        away   = f.get("away", {})

        utc_time = status.get("utcTime", "")
        if not utc_time:
            return None

        dt    = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
        fecha = dt.strftime("%Y-%m-%d")
        hora  = dt.strftime("%H:%M")

        finished  = status.get("finished", False)
        started   = status.get("started", False)
        cancelled = status.get("cancelled", False)
        if cancelled:
            return None
        en_curso = started and not finished

        h_score = home.get("score") if (finished or en_curso) else None
        a_score = away.get("score") if (finished or en_curso) else None

        involucra_cai = (home.get("id") == TEAM_ID or away.get("id") == TEAM_ID)

        return {
            "id":            f.get("id"),
            "fecha":         fecha,
            "hora":          hora,
            "local":         home.get("name"),
            "local_id":      home.get("id"),
            "visita":        away.get("name"),
            "visita_id":     away.get("id"),
            "goles_local":   int(h_score) if h_score is not None else None,
            "goles_visita":  int(a_score) if a_score is not None else None,
            "terminado":     finished,
            "en_curso":      en_curso,
            "involucra_cai": involucra_cai,
            "page_url":      f.get("pageUrl", ""),
        }
    except Exception as e:
        print(f"    ⚠ Error en partido liga {f.get('id')}: {e}")
        return None


def transformar_jugador(m: dict, seccion: str) -> dict:
    """
    Transforma un miembro del squad.
    Estructura real: squad[].title + squad[].members[]
    """
    POS = {
        "keepers":     "Arquero",
        "defenders":   "Defensor",
        "midfielders": "Mediocampista",
        "attackers":   "Delantero",
    }
    return {
        "id":            m.get("id"),
        "nombre":        m.get("name", "—"),
        "numero":        m.get("shirtNumber"),
        "posicion":      POS.get(seccion, seccion),
        "posicion_desc": m.get("positionIdsDesc", ""),
        "nacionalidad":  m.get("ccode", ""),
        "pais":          m.get("cname", ""),
        "fecha_nac":     m.get("dateOfBirth", ""),
        "edad":          m.get("age"),
        "altura":        m.get("height"),
        "rating":        m.get("rating"),
        "goles":         m.get("goals", 0),
        "asistencias":   m.get("assists", 0),
        "amarillas":     m.get("ycards", 0),
        "rojas":         m.get("rcards", 0),
        "lesionado":     bool(m.get("injured", False)),
        "lesion_retorno": (m.get("injury") or {}).get("expectedReturn"),
        "valor_mercado": m.get("transferValue"),
    }


def transformar_fila_tabla(row: dict) -> dict:
    """
    Estructura real confirmada: idx, name, id, played, wins, draws, losses,
    scoresStr ("24-20"), goalConDiff, pts
    """
    partes = row.get("scoresStr", "0-0").split("-")
    gf = int(partes[0]) if len(partes) > 0 and partes[0].isdigit() else 0
    gc = int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else 0
    return {
        "pos":        row.get("idx"),
        "equipo":     row.get("name"),
        "equipo_id":  row.get("id"),
        "pj":         row.get("played", 0),
        "g":          row.get("wins", 0),
        "e":          row.get("draws", 0),
        "p":          row.get("losses", 0),
        "gf":         gf,
        "gc":         gc,
        "dg":         row.get("goalConDiff", 0),
        "pts":        row.get("pts", 0),
        "es_cai":     row.get("id") == TEAM_ID,
        "qual_color": row.get("qualColor"),
        "forma":      row.get("form", []),
    }


def transformar_transferencia(t: dict, tipo: str) -> dict:
    return {
        "nombre":       t.get("name"),
        "jugador_id":   t.get("playerId"),
        "posicion":     (t.get("position") or {}).get("label"),
        "tipo":         tipo,
        "prestamo":     t.get("onLoan", False),
        "club_origen":  t.get("fromClub"),
        "club_destino": t.get("toClub"),
        "fee":          (t.get("fee") or {}).get("feeText"),
        "fecha":        (t.get("transferDate") or "")[:10],
    }


# ══════════════════════════════════════════════════
#  EXTRACCIÓN — basada en estructura real del JSON
# ══════════════════════════════════════════════════

def extraer_fixtures(data: dict) -> tuple[list, str | None]:
    """
    Extrae fixtures de allFixtures.fixtures.
    Devuelve (lista_partidos, previousFixturesUrl)
    """
    all_fix = data.get("fixtures", {}).get("allFixtures", {})
    raw     = all_fix.get("fixtures", [])
    prev_url = all_fix.get("previousFixturesUrl")  # URL para paginación histórica

    partidos = [t for f in raw if (t := transformar_fixture(f))]
    print(f"     {len(partidos)} partidos en temporada actual")
    return partidos, prev_url


def extraer_fixtures_historicos(prev_url: str, max_paginas: int = 5) -> list:
    """
    Pagina hacia atrás usando previousFixturesUrl para obtener
    partidos de temporadas anteriores.
    """
    todos = []
    url   = prev_url
    pagina = 1

    while url and pagina <= max_paginas:
        print(f"     Página histórica {pagina}: {url}")
        try:
            data = get(url)
            raw = []
            if isinstance(data, list):
                raw = data
            elif isinstance(data, dict):
                raw = (
                    data.get("fixtures") or
                    data.get("allFixtures", {}).get("fixtures") or
                    []
                )

            partidos = [t for f in raw if (t := transformar_fixture(f))]
            todos.extend(partidos)
            print(f"       → {len(partidos)} partidos")

            if isinstance(data, dict):
                url = data.get("previousFixturesUrl") or data.get("allFixtures", {}).get("previousFixturesUrl")
            else:
                url = None

            pagina += 1
        except Exception as e:
            print(f"       ⚠ Error en paginación: {e}")
            break

    return todos


def extraer_plantel(data: dict) -> list:
    """
    squad está en overview.squad o squad.squad.
    Estructura: [ {title: "keepers", members: [...]}, ... ]
    """
    squad_sections = (
        data.get("overview", {}).get("squad") or
        data.get("squad", {}).get("squad") or
        []
    )
    jugadores = []
    for sec in squad_sections:
        titulo = sec.get("title", "")
        if titulo == "coach":
            continue
        for m in sec.get("members", []):
            jugadores.append(transformar_jugador(m, titulo))

    print(f"     {len(jugadores)} jugadores")
    return jugadores


def extraer_tabla(data: dict) -> list:
    """
    Versión simple: devuelve solo la primera zona donde está CAI.
    Usada para el widget compacto en portada.
    """
    contenedores = data.get("table") or data.get("overview", {}).get("table") or []

    for contenedor in contenedores:
        tables = contenedor.get("data", {}).get("tables", [])
        for t in tables:
            rows = t.get("table", {}).get("all", [])
            con_datos = [r for r in rows if r.get("played", 0) > 0]
            tiene_cai = any(r.get("id") == TEAM_ID for r in con_datos)
            if con_datos and tiene_cai:
                tabla = [transformar_fila_tabla(r) for r in con_datos]
                print(f"     Tabla (portada): {t.get('leagueName')} ({len(tabla)} equipos)")
                return tabla

    print("     ⚠ No se encontró tabla con datos")
    return []


def extraer_liga(data: dict) -> dict:
    """
    Extrae toda la información de la liga actual:
    - Metadatos (nombre, id, temporada, fecha/round actual)
    - Todas las zonas de la tabla (Apertura A, B, Clausura, etc.)
    - Fixture completo de la fecha actual (todos los partidos, no solo CAI)
    - Top goleadores y asistentes de la liga
    """
    contenedores = data.get("table") or data.get("overview", {}).get("table") or []

    # ── Metadatos de la competencia ──
    # Tomamos el nombre/id del primer contenedor que tenga datos
    liga_nombre = None
    liga_id     = None
    liga_season = data.get("details", {}).get("latestSeason")

    # ── Todas las zonas de la tabla ──
    zonas = []
    for contenedor in contenedores:
        cdata  = contenedor.get("data", {})
        tables = cdata.get("tables", [])

        for t in tables:
            rows      = t.get("table", {}).get("all", [])
            con_datos = [r for r in rows if r.get("played", 0) > 0]
            if not con_datos:
                continue

            nombre_zona = t.get("leagueName") or t.get("name") or "Zona"
            league_id   = t.get("leagueId") or t.get("id")

            if not liga_nombre:
                liga_nombre = nombre_zona
                liga_id     = league_id

            zonas.append({
                "nombre":     nombre_zona,
                "liga_id":    league_id,
                "tiene_cai":  any(r.get("id") == TEAM_ID for r in con_datos),
                "tabla":      [transformar_fila_tabla(r) for r in con_datos],
            })

    print(f"     {len(zonas)} zona(s) de tabla extraídas")

    # ── Fixture de la fecha actual ──
    # FotMob agrupa fixtures por ronda en fixtures.fixtures[]
    # o a veces en overview.fixtures — tomamos los de la ronda más reciente con partidos
    fecha_actual_label = None
    partidos_fecha = []

    all_fix = data.get("fixtures", {}).get("allFixtures", {})
    fixtures_raw = all_fix.get("fixtures", [])

    # Buscamos la "ronda" que contiene el último partido jugado o el próximo pendiente
    # Los fixtures de CAI tienen tournament.round — usamos eso como referencia
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Encontrar la ronda actual/próxima de CAI
    ronda_ref = None
    for f in fixtures_raw:
        tourn = f.get("tournament", {})
        status = f.get("status", {})
        utc = status.get("utcTime", "")
        if not utc:
            continue
        fecha_f = utc[:10]
        round_name = tourn.get("round") or tourn.get("roundId")
        if round_name and fecha_f >= hoy:
            ronda_ref = round_name
            fecha_actual_label = round_name
            break

    # Si no hay próximos, tomamos la última ronda jugada
    if not ronda_ref:
        for f in reversed(fixtures_raw):
            tourn = f.get("tournament", {})
            status = f.get("status", {})
            if status.get("finished"):
                ronda_ref = tourn.get("round") or tourn.get("roundId")
                fecha_actual_label = ronda_ref
                break

    # Filtrar todos los partidos de esa ronda (incluye todos los equipos)
    # FotMob a veces incluye otros partidos de la misma liga en fixtures
    if ronda_ref:
        for f in fixtures_raw:
            tourn = f.get("tournament", {})
            if (tourn.get("round") or tourn.get("roundId")) == ronda_ref:
                p = transformar_partido_liga(f)
                if p:
                    partidos_fecha.append(p)

    # Si no logramos armar la fecha con rondas, al menos ponemos los de CAI
    if not partidos_fecha:
        for f in fixtures_raw:
            p = transformar_partido_liga(f)
            if p:
                partidos_fecha.append(p)
        partidos_fecha = partidos_fecha[:10]  # limitar

    partidos_fecha.sort(key=lambda x: x.get("fecha", "") + x.get("hora", ""))
    print(f"     Fecha actual: '{fecha_actual_label}' — {len(partidos_fecha)} partido(s)")

    # ── Top jugadores de la liga (de CAI, ya los tenemos) ──
    top = (
        data.get("overview", {}).get("topPlayers") or
        data.get("topPlayers") or
        {}
    )

    def mapear_top(players: list) -> list:
        return [
            {
                "id":     p.get("id"),
                "nombre": p.get("name"),
                "equipo": p.get("teamName"),
                "equipo_id": p.get("teamId"),
                "valor":  p.get("value"),
                "rank":   p.get("rank"),
            }
            for p in (players or [])
        ]

    top_jugadores = {
        "goleadores":   mapear_top((top.get("byGoals")   or {}).get("players", [])),
        "asistidores":  mapear_top((top.get("byAssists") or {}).get("players", [])),
        "mejor_rating": mapear_top((top.get("byRating")  or {}).get("players", [])),
    }

    return {
        "nombre":          liga_nombre or "Liga Profesional",
        "liga_id":         liga_id,
        "temporada":       liga_season,
        "fecha_label":     fecha_actual_label,
        "zonas":           zonas,
        "partidos_fecha":  partidos_fecha,
        "top_jugadores":   top_jugadores,
    }


def extraer_top_jugadores(data: dict) -> dict:
    """
    topPlayers está en overview.topPlayers o en stats.
    Tiene byGoals, byAssists, byRating — cada uno con .players[]
    """
    top = (
        data.get("overview", {}).get("topPlayers") or
        data.get("topPlayers") or
        {}
    )

    def mapear(players: list) -> list:
        return [
            {"id": p.get("id"), "nombre": p.get("name"),
             "valor": p.get("value"), "rank": p.get("rank")}
            for p in players
        ]

    resultado = {
        "goleadores":   mapear((top.get("byGoals")   or {}).get("players", [])),
        "asistidores":  mapear((top.get("byAssists") or {}).get("players", [])),
        "mejor_rating": mapear((top.get("byRating")  or {}).get("players", [])),
    }

    if resultado["goleadores"]:
        g = resultado["goleadores"][0]
        print(f"     Goleador CAI: {g['nombre']} ({g['valor']} goles)")

    return resultado


def extraer_transferencias(data: dict) -> dict:
    """
    Transfers en data.transfers.data o data.overview.transfers.data
    Con claves "Players in", "Players out", "Contract extension"
    """
    tdata = (
        data.get("transfers", {}).get("data") or
        data.get("overview", {}).get("transfers", {}).get("data") or
        {}
    )
    resultado = {
        "entradas": [transformar_transferencia(t, "entrada") for t in tdata.get("Players in", [])],
        "salidas":  [transformar_transferencia(t, "salida")  for t in tdata.get("Players out", [])],
    }
    print(f"     {len(resultado['entradas'])} entradas, {len(resultado['salidas'])} salidas")
    return resultado


def extraer_proximo_y_ultimo(data: dict) -> tuple[dict | None, dict | None]:
    """nextMatch y lastMatch están en fixtures.allFixtures o en overview."""
    all_fix  = data.get("fixtures", {}).get("allFixtures", {})
    overview = data.get("overview", {})

    next_raw = all_fix.get("nextMatch") or overview.get("nextMatch")
    last_raw = all_fix.get("lastMatch") or overview.get("lastMatch")

    proximo = transformar_fixture(next_raw) if next_raw else None
    ultimo  = transformar_fixture(last_raw) if last_raw else None
    return proximo, ultimo


# ══════════════════════════════════════════════════
#  GUARDAR
# ══════════════════════════════════════════════════

def guardar(nombre: str, data) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{nombre}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    kb = path.stat().st_size / 1024
    print(f"  💾 {path.name} ({kb:.1f} KB)")


# ══════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Scraper FotMob — CAI")
    parser.add_argument("--check",   action="store_true", help="Solo verificar conectividad")
    parser.add_argument("--history", action="store_true", help="Scrapear partidos históricos paginando")
    parser.add_argument("--pages",   type=int, default=3, help="Páginas históricas a traer (default: 3)")
    parser.add_argument("--raw",     action="store_true", help="Guardar JSON crudo para debug")
    args = parser.parse_args()

    print("\n⚽ CAI Scraper — FotMob")
    print(f"   Team ID : {TEAM_ID}")
    print(f"   URL     : {TEAM_URL}")
    print(f"   Output  : {OUTPUT_DIR}\n")

    # ── Fetch principal ──
    print("[1] Descargando temporada actual...")
    try:
        data = get(TEAM_URL)
    except Exception as e:
        print(f"✗ No se pudo conectar con FotMob: {e}")
        sys.exit(1)

    if args.check:
        nombre  = data.get("details", {}).get("name", "?")
        season  = data.get("details", {}).get("latestSeason", "?")
        print(f"✓ OK — equipo: {nombre}, temporada: {season}")
        return

    if args.raw:
        guardar("fotmob_raw", data)

    # ── Procesar ──
    print("\n[2] Procesando datos...\n")

    print("  → Fixtures actuales:")
    fixtures_actuales, prev_url = extraer_fixtures(data)

    # Histórico opcional
    fixtures_historicos = []
    if args.history and prev_url:
        print(f"\n  → Fixtures históricos (hasta {args.pages} páginas):")
        fixtures_historicos = extraer_fixtures_historicos(prev_url, max_paginas=args.pages)
        print(f"     Total histórico: {len(fixtures_historicos)} partidos")

    # Combinar y ordenar por fecha desc
    todos_los_fixtures = fixtures_actuales + fixtures_historicos
    todos_los_fixtures.sort(key=lambda x: x.get("fecha", ""), reverse=True)

    guardar("partidos", todos_los_fixtures)
    print(f"     Total guardado: {len(todos_los_fixtures)} partidos")

    print("\n  → Próximo / último partido:")
    proximo, ultimo = extraer_proximo_y_ultimo(data)
    guardar("proximo_partido", proximo or {})
    guardar("ultimo_partido",  ultimo  or {})
    if proximo:
        print(f"     Próximo: {proximo['rival']} el {proximo['fecha']}")
    if ultimo:
        print(f"     Último:  {ultimo['rival']} {ultimo['goles_favor']}-{ultimo['goles_contra']} ({ultimo['resultado']})")

    print("\n  → Plantel:")
    guardar("plantel", extraer_plantel(data))

    print("\n  → Tabla de posiciones (portada):")
    guardar("standings", extraer_tabla(data))

    print("\n  → Liga actual (tabla completa + fecha + tops):")
    guardar("liga", extraer_liga(data))

    print("\n  → Top jugadores CAI:")
    guardar("top_jugadores", extraer_top_jugadores(data))

    print("\n  → Transferencias:")
    guardar("transferencias", extraer_transferencias(data))

    # Metadata
    guardar("meta", {
        "ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
        "team_id":   TEAM_ID,
        "equipo":    data.get("details", {}).get("name", "Independiente"),
        "temporada": data.get("details", {}).get("latestSeason"),
        "total_partidos": len(todos_los_fixtures),
    })

    print(f"\n✅ Listo — {OUTPUT_DIR}\n")


if __name__ == "__main__":
    main()