"""Configuração da Área 1: municípios, provedores e leitura da planilha."""
from __future__ import annotations

from pathlib import Path

from config.area1_municipios import EXERCICIO, MUNICIPIOS_AREA1, PLANILHA_ORIGEM
from config.planilha import RAIZ_PROJETO, ler_planilha, localizar_planilha


def carregar_municipios(raiz: Path | str = RAIZ_PROJETO) -> tuple[list[dict], str, list[str]]:
    """Retorna (municipios, fonte, avisos).

    Prioridade: planilha .xlsx presente na raiz (sempre a versão mais recente)
    -> lista gerada em ``config/area1_municipios.py``.
    """
    planilha = localizar_planilha(raiz)
    if planilha is not None:
        try:
            municipios, avisos = ler_planilha(planilha)
            if municipios:
                return municipios, f"Planilha {planilha.name}", avisos
        except Exception as exc:  # planilha corrompida/aberta: cai para o config
            avisos = [f"Falha ao ler {planilha.name}: {exc}"]
            if MUNICIPIOS_AREA1:
                return list(MUNICIPIOS_AREA1), "config/area1_municipios.py", avisos
            return [], "—", avisos
    if MUNICIPIOS_AREA1:
        return list(MUNICIPIOS_AREA1), f"config/area1_municipios.py ({PLANILHA_ORIGEM})", []
    return [], "—", ["Planilha .xlsx da Área 1 não encontrada na raiz do projeto."]


__all__ = ["EXERCICIO", "MUNICIPIOS_AREA1", "carregar_municipios", "ler_planilha", "localizar_planilha"]
