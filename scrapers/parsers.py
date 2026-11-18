"""Parsers genéricos para páginas e respostas JSON dos portais da transparência.

Os portais municipais variam muito de layout; por isso a extração é baseada em
heurísticas de cabeçalho (``mapear_campo``) aplicadas tanto a tabelas HTML
quanto a chaves de objetos JSON.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrapers.keywords import normalizar

CAMPOS = ("numero", "data_assinatura", "contratada", "cnpj", "objeto", "valor", "vigencia")

# Ordem importa: "contratada" deve ser testado antes de "numero" (ambos contêm "contrat").
_REGRAS_CAMPO: list[tuple[str, tuple[str, ...]]] = [
    ("data_assinatura", ("vigencia inicial", "inicio da vigencia", "inicio vigencia")),
    ("cnpj", ("cnpj", "cpf/cnpj", "cpf_cnpj", "cpfcnpj", "documento do fornecedor", "inscricao")),
    ("contratada", ("contratad", "fornecedor", "empresa", "credor", "razao social", "razaosocial",
                    "favorecido", "nome do fornecedor", "beneficiario")),
    ("objeto", ("objeto", "descricao", "historico", "finalidade", "especificacao", "resumo")),
    ("vigencia", ("vigencia", "vencimento", "termino", "data final", "datafim", "data fim", "prazo", "validade")),
    ("data_assinatura", ("assinatura", "celebra", "data do contrato", "datacontrato", "data contrato",
                         "data inicio", "datainicio", "data", "dt")),
    ("valor", ("valor", "vlr", "montante", "preco")),
    ("numero", ("numero", "nº", "n°", "no contrato", "contrato", "num", "codigo", "processo")),
]


def mapear_campo(cabecalho: str | None) -> str | None:
    """Mapeia o texto de um cabeçalho/chave para um campo padronizado."""
    h = normalizar(cabecalho).replace("_", " ")
    if not h:
        return None
    for campo, termos in _REGRAS_CAMPO:
        if any(t in h for t in termos):
            return campo
    return None


# --------------------------------------------------------------------------- #
# Conversões de valor/data/documento
# --------------------------------------------------------------------------- #
def parse_valor(v: Any) -> float | None:
    """'R$ 1.234.567,89' -> 1234567.89 ; aceita números e '1234.56'."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if not s or s in "-.,":
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


_FORMATOS_DATA = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y")


def parse_data(v: Any) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    m = re.search(r"/Date\((\d+)", s)  # formato .NET: /Date(1767225600000)/
    if m:
        return datetime.utcfromtimestamp(int(m.group(1)) / 1000).date()
    m = re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}", s)
    if not m:
        return None
    trecho = m.group(0)
    for fmt in _FORMATOS_DATA:
        try:
            return datetime.strptime(trecho, fmt).date()
        except ValueError:
            continue
    return None


def formatar_cnpj(v: Any) -> str:
    d = re.sub(r"\D", "", str(v or ""))
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return str(v or "").strip()


_CNPJ_RE = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")


def extrair_cnpj(texto: str | None) -> str:
    m = _CNPJ_RE.search(texto or "")
    return formatar_cnpj(m.group(0)) if m else ""


# --------------------------------------------------------------------------- #
# Classificação de links de documentos
# --------------------------------------------------------------------------- #
def classificar_link(texto: str | None, href: str | None) -> str | None:
    """Classifica um link como 'os', 'empenho', 'contrato' ou 'detalhe'."""
    t = normalizar(f"{texto or ''} {href or ''}")
    rotulo = normalizar(texto).strip(" .")
    if not href or href.startswith(("javascript:void", "#", "mailto:")):
        return None
    if rotulo in ("os", "o.s") or re.search(
            r"ordem (de )?servic|ordem_servico|ordemservico|ordem-de-servico|\bo\.s\b", t):
        return "os"
    if re.search(r"empenh|pagament|liquidac|nota fiscal|despesa", t):
        return "empenho"
    if re.search(r"contrato|\.pdf|arquivo|download|anexo|documento|visualizar|termo", t):
        return "contrato"
    if re.search(r"detalh|consultar|ver mais|abrir|exibir", t):
        return "detalhe"
    return None


def links_documentos(soup_ou_tag, base_url: str) -> dict[str, str]:
    """Extrai o primeiro link de cada tipo (contrato/os/empenho/detalhe)."""
    achados: dict[str, str] = {}
    for a in soup_ou_tag.find_all("a", href=True):
        tipo = classificar_link(a.get_text(" ", strip=True) + " " + (a.get("title") or ""), a["href"])
        if tipo and tipo not in achados:
            achados[tipo] = urljoin(base_url, a["href"])
    return achados


# --------------------------------------------------------------------------- #
# Tabelas HTML
# --------------------------------------------------------------------------- #
def _cabecalhos(tabela) -> list[str]:
    thead = tabela.find("thead")
    linha = (thead.find("tr") if thead else None) or tabela.find("tr")
    if not linha:
        return []
    return [c.get_text(" ", strip=True) for c in linha.find_all(["th", "td"])]


def extrair_registros_html(html: str, base_url: str) -> list[dict]:
    """Converte as tabelas de contratos de uma página em registros padronizados."""
    soup = BeautifulSoup(html, "lxml")
    registros: list[dict] = []
    for tabela in soup.find_all("table"):
        cab = _cabecalhos(tabela)
        mapa = {i: mapear_campo(h) for i, h in enumerate(cab)}
        campos = {c for c in mapa.values() if c}
        if not ({"objeto"} <= campos and campos & {"numero", "valor", "contratada"}):
            continue  # tabela não parece de contratos
        linhas = tabela.find("tbody").find_all("tr") if tabela.find("tbody") else tabela.find_all("tr")[1:]
        for tr in linhas:
            celulas = tr.find_all(["td", "th"])
            if len(celulas) < 2:
                continue
            reg: dict[str, Any] = {}
            for i, td in enumerate(celulas):
                campo = mapa.get(i)
                if campo and not reg.get(campo):
                    reg[campo] = td.get_text(" ", strip=True)
            if not reg.get("objeto"):
                continue
            reg["_links"] = links_documentos(tr, base_url)
            registros.append(reg)
    return registros


def extrair_registros_devexpress(html: str, base_url: str) -> list[dict]:
    """Grades DevExpress (ASPxGridView), usadas pelo Fiorilli SCPI: o cabeçalho fica em
    células ``dxgvHeader`` e as linhas em ``tr[id*=DXDataRow]``."""
    soup = BeautifulSoup(html, "lxml")
    registros: list[dict] = []
    for tabela in soup.find_all("table", id=re.compile(r"DXMainTable$")):
        cab = [h.get_text(" ", strip=True) for h in tabela.select("td[class*=dxgvHeader]")]
        mapa = {i: mapear_campo(h) for i, h in enumerate(cab)}
        if "objeto" not in mapa.values():
            continue
        for tr in tabela.find_all("tr", id=re.compile(r"DXDataRow\d+$")):
            reg: dict[str, Any] = {}
            for i, td in enumerate(tr.find_all("td", recursive=False)):
                campo = mapa.get(i)
                if campo and not reg.get(campo):
                    reg[campo] = td.get_text(" ", strip=True)
            if reg.get("objeto"):
                reg["_links"] = links_documentos(tr, base_url)
                registros.append(reg)
    return registros


def links_para_contratos(html: str, base_url: str) -> list[str]:
    """Na página inicial, encontra links de menu que levam à consulta de contratos."""
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []
    for a in soup.find_all("a", href=True):
        txt = normalizar(a.get_text(" ", strip=True) + " " + a["href"])
        if "contrat" in txt and not a["href"].startswith(("javascript", "#", "mailto")):
            u = urljoin(base_url, a["href"])
            if u not in urls:
                urls.append(u)
    return urls[:4]


# --------------------------------------------------------------------------- #
# JSON (Fiorilli VersaoJson e APIs REST simples)
# --------------------------------------------------------------------------- #
def _listas_em(obj: Any) -> Iterable[list]:
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _listas_em(v)


def extrair_registros_json(dados: Any, base_url: str) -> list[dict]:
    registros: list[dict] = []
    for lista in _listas_em(dados):
        for item in lista:
            reg: dict[str, Any] = {"_links": {}}
            for chave, valor in item.items():
                if isinstance(valor, (dict, list)):
                    continue
                sval = "" if valor is None else str(valor)
                if sval.startswith(("http", "/")) and len(sval) > 4:
                    tipo = classificar_link(chave, sval)
                    if tipo:
                        reg["_links"].setdefault(tipo, urljoin(base_url, sval))
                        continue
                campo = mapear_campo(chave)
                if campo and not reg.get(campo):
                    reg[campo] = valor
            if reg.get("objeto"):
                registros.append(reg)
        if registros:
            break
    return registros
