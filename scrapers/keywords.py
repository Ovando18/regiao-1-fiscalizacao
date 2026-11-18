"""Filtro semântico de objetos de contratos — Engenharia, Agronomia e Geociências.

As palavras-chave são radicais normalizados (sem acentos, minúsculas) e casam
no início de palavra: ``paviment`` captura "pavimentação", "pavimentar" etc.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

AREA_TODAS = "Todas"

AREAS_TECNICAS: dict[str, list[str]] = {
    "Engenharia Civil/Obras": [
        "obra", "engenhar", "paviment", "recapeament", "asfalt", "tapa buraco",
        "drenag", "reforma", "ampliac", "construc", "constru", "edificac",
        "terraplan", "ponte", "estrada", "vicinal", "cascalh", "bueiro",
        "galeria pluvial", "meio fio", "meio-fio", "sarjeta", "calcada",
        "manutencao predial", "alvenaria", "cobertura", "telhado",
        "restauracao", "revitalizac", "urbanizac", "infraestrutura",
        "saneamento", "esgot", "abastecimento de agua", "rede de agua",
        "estacao de tratamento", "poco artesiano", "fiscalizacao de obra",
        "muro", "quadra poliesportiva", "unidade basica de saude",
    ],
    "Engenharia Elétrica/Mecânica": [
        "eletric", "iluminacao publica", "iluminacao", "subestac",
        "rede de distribuicao", "spda", "para-raio", "pararraio",
        "energia solar", "fotovolta", "gerador", "climatizac",
        "ar condicionado", "ar-condicionado", "refrigerac", "elevador",
        "mecanic", "caldeira", "telecomunicac", "cabeamento estruturado",
    ],
    "Agronomia/Meio Ambiente": [
        "agronom", "agricol", "agropecuar", "licenciamento ambiental",
        "ambiental", "reflorestament", "recuperacao de area degradada",
        "prad", "arboriz", "poda", "paisagis", "rocada", "capina",
        "defensivo", "correcao de solo", "calcario", "irrigac",
        "residuos solidos", "aterro sanitario", "coleta de lixo",
        "inventario florestal", "manejo",
    ],
    "Geociências/Topografia": [
        "topograf", "georreferenc", "geodes", "geotecn", "geolog",
        "sondagem", "levantamento planialtimetric", "planialtimetr",
        "aerofotogramet", "cadastro tecnico", "cartograf", "batimetr",
        "regularizacao fundiaria", "perfuracao de poco", "hidrogeolog",
    ],
    "Projetos/Consultoria Técnica": [
        "projeto", "laudo", "consultoria tecnica", "assessoria tecnica",
        "pericia", "vistoria", "estudo de viabilidade", "plano diretor",
        "orcamento de obra", "responsabilidade tecnica",
        "supervisao de obra", "gerenciamento de obra", "plano de manejo",
        "estudo de impacto", "eia/rima", "avaliacao de imove",
    ],
}

# Expressões que geram falso positivo frequente e devem ser ignoradas.
EXCLUSOES = [
    "projeto de lei", "mao de obra terceirizada para limpeza",
    "projeto pedagogico", "projeto social", "projeto cultural",
]

TODAS_PALAVRAS: list[str] = sorted({p for lst in AREAS_TECNICAS.values() for p in lst})


def normalizar(texto: str | None) -> str:
    """Remove acentos, converte para minúsculas e compacta espaços."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.lower()).strip()


@lru_cache(maxsize=None)
def _regex(palavra: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(palavra.strip()))


def _limpar_exclusoes(texto_norm: str) -> str:
    for exc in EXCLUSOES:
        texto_norm = texto_norm.replace(exc, " ")
    return texto_norm


def classificar_areas(objeto: str | None) -> list[str]:
    """Retorna as áreas técnicas cujo vocabulário aparece no objeto."""
    t = _limpar_exclusoes(normalizar(objeto))
    if not t:
        return []
    return [area for area, palavras in AREAS_TECNICAS.items()
            if any(_regex(p).search(t) for p in palavras)]


def eh_objeto_tecnico(objeto: str | None) -> bool:
    """True se o objeto pertence ao escopo Engenharia/Agronomia/Geociências."""
    return bool(classificar_areas(objeto))
