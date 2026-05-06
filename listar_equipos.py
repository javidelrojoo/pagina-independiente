"""
listar_equipos.py
=================
Lee partidos.json y standings.json y lista todos los equipos
con sus IDs de FotMob, para saber qué logos tenés que conseguir.

Uso:
    python listar_equipos.py

Resultado: una tabla con ID | Nombre | ¿Tiene logo?
Los logos van en:  public/img/equipos/{id}.png
"""

import json
from pathlib import Path

DATA_DIR  = Path(__file__).parent / "public" / "data"
LOGOS_DIR = Path(__file__).parent / "public" / "img" / "equipos"
TEAM_ID   = 10078  # Independiente

def cargar(nombre):
    p = DATA_DIR / f"{nombre}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))

equipos = {}  # id -> nombre

# Independiente siempre
equipos[TEAM_ID] = "Independiente (CAI)"

# Desde partidos.json
partidos = cargar("partidos") or []
for p in partidos:
    rid = p.get("rival_id")
    rnom = p.get("rival")
    if rid and rnom:
        equipos[rid] = rnom

# Desde standings.json
standings = cargar("standings") or []
for s in standings:
    eid = s.get("equipo_id")
    enom = s.get("equipo")
    if eid and enom:
        equipos[eid] = enom

# Ordenar por nombre
ordenados = sorted(equipos.items(), key=lambda x: x[1])

print(f"\n{'ID':>8}  {'¿Logo?':6}  Nombre")
print("-" * 50)
for eid, nombre in ordenados:
    tiene = "  ✓" if (LOGOS_DIR / f"{eid}.png").exists() else "  ✗"
    marcador = " ← TU EQUIPO" if eid == TEAM_ID else ""
    print(f"{eid:>8}  {tiene}      {nombre}{marcador}")

faltantes = [(eid, nom) for eid, nom in ordenados if not (LOGOS_DIR / f"{eid}.png").exists()]
print(f"\nTotal equipos: {len(ordenados)}")
print(f"Con logo:      {len(ordenados) - len(faltantes)}")
print(f"Sin logo:      {len(faltantes)}")

if faltantes:
    print(f"\nFaltan logos para:")
    for eid, nom in faltantes:
        print(f"  public/img/equipos/{eid}.png   ← {nom}")

print(f"\nLos logos van en: public/img/equipos/{{id}}.png")
print(f"Formato recomendado: PNG con fondo transparente, 64×64 px mínimo\n")
