"""Leitura da planilha .xlsx da Área 1 (municípios + URLs dos portais).

A leitura é tolerante ao layout: localiza a linha de cabeçalho, identifica a
coluna de município e a(s) coluna(s) de URL (inclusive hiperlinks embutidos em
células cujo texto não é a URL), e filtra a Área 1 quando houver coluna
"Área"/"Regional".
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import BinaryIO

from openpyxl import load_workbook

from config.provedores import detectar_por_url, url_consulta_contratos
from scrapers.keywords import normalizar

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

_URL_RE = re.compile(r"(https?://[^\s\"'<>]+|www\.[^\s\"'<>]+|[a-z0-9.-]+\.(?:gov|com|net|org)\.br[^\s\"'<>]*)", re.I)


def localizar_planilha(raiz: Path | str = RAIZ_PROJETO) -> Path | None:
    """Retorna a planilha .xlsx da raiz (prioriza nomes com 'area'/'munic')."""
    raiz = Path(raiz)
    candidatas = [p for p in raiz.glob("*.xlsx") if not p.name.startswith("~$")]
    if not candidatas:
        return None

    def peso(p: Path) -> tuple[int, float]:
        n = normalizar(p.stem)
        return (-(("area" in n) + ("munic" in n) + ("transpar" in n)), -p.stat().st_mtime)

    return sorted(candidatas, key=peso)[0]


def _url_da_celula(cell) -> str | None:
    """URL da célula. Prefere a URL escrita no texto (pode conter rotas '#/...' que o
    hiperlink do Excel descarta, como nas entidades Betha Cloud); senão, o hiperlink."""
    texto_url = None
    if cell.value is not None:
        m = _URL_RE.search(str(cell.value))
        if m:
            texto_url = m.group(1).rstrip(".,;)")
            if not texto_url.lower().startswith("http"):
                texto_url = "https://" + texto_url
            texto_url = re.sub(r"/#$", "/", texto_url)
    link = cell.hyperlink.target.strip() if cell.hyperlink is not None and cell.hyperlink.target else None
    return texto_url or link


def _limpar_nome(nome: str) -> str:
    n = re.sub(r"(?i)^\s*(prefeitura( municipal)?|munic[ií]pio)\s+(de|do|da)\s+", "", str(nome))
    n = re.sub(r"\s*[-/]\s*MS\s*$", "", n, flags=re.I)
    return re.sub(r"\s+", " ", n).strip()


def _achar_cabecalho(linhas: list[tuple]) -> int | None:
    for i, linha in enumerate(linhas[:15]):
        textos = [normalizar(c.value) for c in linha if c.value not in (None, "")]
        if len(textos) >= 2 and any(
                (len(t) <= 30 and "munic" in t) or t in ("cidade", "prefeitura") for t in textos):
            return i
    return None


def _indices(cabecalho: list[str]) -> dict[str, list[int]]:
    idx: dict[str, list[int]] = {"municipio": [], "url": [], "contratos": [], "provedor": [], "area": []}
    for i, h in enumerate(cabecalho):
        if not h:
            continue
        if "munic" in h or h in ("cidade", "prefeitura"):
            idx["municipio"].append(i)
        elif "contrat" in h and any(k in h for k in ("url", "link", "consulta", "pagina")):
            idx["contratos"].append(i)
        elif any(k in h for k in ("url", "link", "portal", "site", "transpar", "endereco")):
            idx["url"].append(i)
        elif any(k in h for k in ("provedor", "sistema", "plataforma", "fornecedor do portal")):
            idx["provedor"].append(i)
        elif h.startswith("area") or h.startswith("regiao") or "regional" in h or "inspetoria" in h:
            idx["area"].append(i)
    # Prioriza a coluna "transparência" quando houver mais de uma URL.
    idx["url"].sort(key=lambda i: 0 if "transpar" in cabecalho[i] else 1)
    return idx


def _eh_area1(valor) -> bool:
    v = normalizar(valor)
    return bool(re.fullmatch(r"(area\s*)?(0?1|i|um)", v)) or v.startswith("area 1")


def ler_planilha(origem: Path | str | BinaryIO | bytes) -> tuple[list[dict], list[str]]:
    """Lê a planilha e devolve (municipios, avisos)."""
    if isinstance(origem, bytes):
        origem = io.BytesIO(origem)
    wb = load_workbook(origem, data_only=True)  # hiperlinks exigem modo não read-only
    avisos: list[str] = []

    abas = sorted(wb.worksheets, key=lambda ws: 0 if re.search(r"area\s*0?1", normalizar(ws.title)) else 1)
    for ws in abas:
        linhas = list(ws.iter_rows())
        if not linhas:
            continue
        h = _achar_cabecalho(linhas)
        if h is None:
            continue
        cab = [normalizar(c.value) for c in linhas[h]]
        idx = _indices(cab)
        if not idx["municipio"]:
            continue

        tem_area = bool(idx["area"])
        municipios: list[dict] = []
        vistos: set[str] = set()
        for linha in linhas[h + 1:]:
            col_m = idx["municipio"][0]
            if col_m >= len(linha) or linha[col_m].value in (None, ""):
                continue
            if tem_area and not _eh_area1(linha[idx["area"][0]].value):
                continue
            nome = _limpar_nome(linha[col_m].value)
            if not nome or normalizar(nome) in vistos:
                continue

            url = None
            for c in idx["url"]:
                if c < len(linha):
                    url = _url_da_celula(linha[c])
                    if url:
                        break
            if not url:  # hiperlink no próprio nome ou URL em qualquer coluna
                url = _url_da_celula(linha[col_m]) or next(
                    (u for u in (_url_da_celula(c) for c in linha) if u), None)

            url_contr = None
            for c in idx["contratos"]:
                if c < len(linha):
                    url_contr = _url_da_celula(linha[c]) or url_contr

            prov = None
            if idx["provedor"] and idx["provedor"][0] < len(linha):
                prov = (str(linha[idx["provedor"][0]].value or "").strip()) or None
            prov = prov or detectar_por_url(url)

            if not url:
                avisos.append(f"{nome}: URL do portal não encontrada na planilha.")
            vistos.add(normalizar(nome))
            municipios.append({
                "municipio": nome,
                "url": url or "",
                "provedor": prov,
                "url_contratos": url_contr or (url_consulta_contratos(url, prov) if url else ""),
            })
        if municipios:
            if tem_area:
                avisos.insert(0, f"Coluna '{linhas[h][idx['area'][0]].value}' detectada na aba '{ws.title}': "
                                 f"filtrados apenas os municípios da Área/Região 1.")
            return sorted(municipios, key=lambda m: normalizar(m["municipio"])), avisos

    return [], avisos + ["Nenhuma aba com coluna 'Município' foi encontrada na planilha."]
