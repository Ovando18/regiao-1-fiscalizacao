"""Gera ``config/area1_municipios.py`` a partir da planilha .xlsx da Área 1.

Uso (na raiz do projeto):
    python scripts/gerar_config_area1.py                 # usa a .xlsx da raiz
    python scripts/gerar_config_area1.py --planilha X.xlsx
"""
from __future__ import annotations

import argparse
import pprint
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from config.planilha import ler_planilha, localizar_planilha  # noqa: E402

MODELO = '''"""Municípios da Área 1 de Fiscalização (Crea-MS) e seus Portais da Transparência.

ARQUIVO GERADO AUTOMATICAMENTE por ``scripts/gerar_config_area1.py``.
Planilha de origem: {origem}
Gerado em: {gerado}

Para atualizar: substitua a planilha .xlsx na raiz do projeto e execute
    python scripts/gerar_config_area1.py
Campos por município:
    municipio      nome oficial do município
    url            URL oficial do Portal da Transparência (planilha)
    provedor       provedor identificado (roteia o coletor em scrapers/collector.py)
    url_contratos  link direto para a consulta de contratos no portal
"""

EXERCICIO = 2026
PLANILHA_ORIGEM = {origem_repr}

MUNICIPIOS_AREA1 = {dados}
'''


def gerar(planilha: Path | None, saida: Path) -> int:
    if planilha is None or not planilha.exists():
        print("ERRO: nenhuma planilha .xlsx encontrada na raiz do projeto.", file=sys.stderr)
        return 1
    municipios, avisos = ler_planilha(planilha)
    for a in avisos:
        print("AVISO:", a)
    if not municipios:
        print("ERRO: nenhum município lido da planilha.", file=sys.stderr)
        return 2
    saida.write_text(MODELO.format(
        origem=planilha.name,
        origem_repr=repr(planilha.name),
        gerado=datetime.now().strftime("%d/%m/%Y %H:%M"),
        dados=pprint.pformat(municipios, width=110, sort_dicts=False),
    ), encoding="utf-8")
    print(f"OK: {len(municipios)} municípios gravados em {saida.relative_to(RAIZ) if saida.is_relative_to(RAIZ) else saida}")
    for m in municipios:
        print(f"  - {m['municipio']:<28} {m['provedor']:<20} {m['url']}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--planilha", type=Path, default=None)
    ap.add_argument("--saida", type=Path, default=RAIZ / "config" / "area1_municipios.py")
    args = ap.parse_args()
    sys.exit(gerar(args.planilha or localizar_planilha(RAIZ), args.saida))
