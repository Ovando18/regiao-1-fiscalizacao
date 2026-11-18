"""Identificação automática do provedor do Portal da Transparência.

A detecção é feita em duas etapas:
1. ``detectar_por_url`` — offline, por padrões de domínio/caminho (usada ao
   gerar ``config/area1_municipios.py`` a partir da planilha);
2. ``detectar_por_html`` — em tempo de coleta, pela "assinatura" do HTML
   (rodapé, scripts, meta tags), refinando provedores marcados como "Outro".
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

FIORILLI = "Fiorilli SCPI 9.0"
BETHA_CLOUD = "Betha Cloud"
BETHA_EGOV = "Betha e-Gov"
QUALITY = "Quality Sistemas"
MEGASOFT = "Megasoft"
CR2 = "CR2"
IPM_ATENDE = "IPM Atende.net"
ELOTECH = "Elotech"
AGILI = "Agili"
OUTRO = "Outro / Genérico"

# Provedores cujo portal é uma SPA (JavaScript) — sem HTML estático de dados.
PROVEDORES_DINAMICOS = {BETHA_CLOUD, IPM_ATENDE, ELOTECH}

_PADROES_URL: list[tuple[str, str]] = [
    (r"betha\.cloud", BETHA_CLOUD),
    (r"e-gov\.betha\.com\.br|egov\.betha", BETHA_EGOV),
    (r"fiorilli|scpi|versaojson|rcmsuporte|:\d{4}/transparencia", FIORILLI),
    (r"qualitysistemas|quality\.", QUALITY),
    (r"megasoft", MEGASOFT),
    (r"cr2\.(co|com\.br|site)|portalcr2|\.cr2\b", CR2),
    (r"atende\.net", IPM_ATENDE),
    (r"elotech", ELOTECH),
    (r"agili", AGILI),
]

_ASSINATURAS_HTML: list[tuple[str, str]] = [
    (r"betha\s*cloud|transparencia\.betha\.cloud", BETHA_CLOUD),
    (r"betha\s*sistemas|e-gov\.betha", BETHA_EGOV),
    (r"fiorilli|scpi", FIORILLI),
    (r"quality\s*sistemas", QUALITY),
    (r"megasoft", MEGASOFT),
    (r"\bcr2\b", CR2),
    (r"atende\.net|ipm\s*sistemas", IPM_ATENDE),
    (r"elotech", ELOTECH),
    (r"agili", AGILI),
]


def detectar_por_url(url: str | None) -> str:
    if not url:
        return OUTRO
    u = url.strip().lower()
    for padrao, prov in _PADROES_URL:
        if re.search(padrao, u):
            return prov
    return OUTRO


def detectar_por_html(html: str | None) -> str | None:
    if not html:
        return None
    trecho = html[-40000:].lower() + html[:20000].lower()
    for padrao, prov in _ASSINATURAS_HTML:
        if re.search(padrao, trecho):
            return prov
    return None


def raiz_fiorilli(url: str) -> str:
    """``http://host:8079/transparencia/qualquer`` -> ``http://host:8079/transparencia/``.

    Procura "/transparencia" apenas no CAMINHO (o domínio pode conter
    "transparencia.", como em transparencia.ivinhema.ms.gov.br)."""
    p = urlsplit(url.strip())
    m = re.search(r"/transparencia", p.path, flags=re.I)
    caminho = (p.path[:m.end()] if m else p.path.rstrip("/") + "/transparencia") + "/"
    return urlunsplit((p.scheme, p.netloc, caminho, "", ""))


def url_consulta_contratos(url: str, provedor: str) -> str:
    """Deriva o link que abre diretamente a consulta de contratos no portal."""
    if not url:
        return url
    base = url.strip()
    low = base.lower()
    if "contrat" in low:
        return base
    if provedor == FIORILLI:
        # Página de contratos do SCPI (a versão JSON é consultada pelo coletor).
        return raiz_fiorilli(base)
    if provedor == BETHA_EGOV:
        return base.rstrip("/") + "/con_contratos.faces" if base.endswith(("/", "transparencia")) else base
    if provedor == BETHA_CLOUD:
        # Rotas SPA: o usuário cai na entidade; a aba de contratos é aberta no portal.
        return base
    # Demais provedores: o coletor descobre o link de contratos navegando na
    # página inicial; aqui devolvemos a URL oficial informada na planilha.
    return base
