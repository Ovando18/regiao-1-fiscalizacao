"""Coletor multi-plataforma de contratos — consulta direta aos Portais da Transparência.

Não utiliza a API do PNCP. Cada município é roteado para um coletor conforme o
provedor identificado em ``config/area1_municipios.py``. Falhas de um portal
nunca interrompem a pesquisa: geram um diagnóstico (``Online``,
``Instável / Timeout`` ou ``Acesso Manual``) com o link direto de consulta.
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Callable, Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import provedores as P
from scrapers.keywords import classificar_areas
from scrapers.parsers import (
    extrair_cnpj,
    extrair_registros_devexpress,
    extrair_registros_html,
    extrair_registros_json,
    formatar_cnpj,
    links_documentos,
    links_para_contratos,
    parse_data,
    parse_valor,
)

STATUS_ONLINE = "Online"
STATUS_INSTAVEL = "Instável / Timeout"
STATUS_MANUAL = "Acesso Manual"

TIMEOUT = (6, 20)  # (conexão, leitura) em segundos
MAX_DETALHES = 20  # páginas de detalhe visitadas por município para achar OS/Empenho
MAX_WORKERS = 8
# Alguns portais municipais usam certificados inválidos. Por segurança a
# verificação TLS fica ligada; defina FISCALIZA_SSL_VERIFY=0 para desativar.
VERIFICAR_SSL = os.environ.get("FISCALIZA_SSL_VERIFY", "1") != "0"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 FiscalizaObras-MS/1.0"
)


class AcessoManual(Exception):
    """O portal respondeu, mas os dados exigem navegação manual/dinâmica."""


@dataclass
class Contrato:
    municipio: str
    numero: str
    data_assinatura: date | None
    contratada: str
    cnpj: str
    objeto: str
    valor: float | None
    vigencia: str
    link_contrato: str | None
    link_os: str | None
    link_empenho: str | None
    link_portal: str
    areas: list[str] = field(default_factory=list)
    provedor: str = ""

    @property
    def docs_localizados(self) -> int:
        return sum(bool(x) for x in (self.link_contrato, self.link_os, self.link_empenho))


@dataclass
class Diagnostico:
    municipio: str
    provedor: str
    status: str
    mensagem: str
    url_portal: str
    url_consulta: str
    tempo_s: float = 0.0
    registros_lidos: int = 0
    contratos_tecnicos: int = 0


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def criar_sessao() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=2, connect=2, read=1, backoff_factor=0.6,
                  status_forcelist=(500, 502, 503, 504), allowed_methods=("GET", "HEAD"))
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=8)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"})
    return s


def _get(sessao: requests.Session, url: str, **kw) -> requests.Response:
    r = sessao.get(url, timeout=TIMEOUT, verify=VERIFICAR_SSL, **kw)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding or "utf-8"
    return r


def _parece_spa(html: str) -> bool:
    low = html.lower()
    texto = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", low, flags=re.S)
    pouco_texto = len(texto.split()) < 120
    marcadores = any(m in low for m in ("<app-root", "ng-app", "id=\"app\"", "id=\"root\"", "__next", "vue"))
    return pouco_texto and marcadores


def _resposta_json(r: requests.Response):
    if "json" in r.headers.get("Content-Type", "").lower() or r.text.lstrip()[:1] in "[{":
        try:
            return r.json()
        except ValueError:
            return None
    return None


# --------------------------------------------------------------------------- #
# Coletores por provedor — cada um retorna (registros_brutos, url_consulta)
# --------------------------------------------------------------------------- #
def _coletar_html(sessao, url: str, municipio: dict) -> tuple[list[dict], str, str]:
    """Consulta HTML/JSON genérica com descoberta do menu 'Contratos'."""
    r = _get(sessao, url)
    html = r.text
    dados = _resposta_json(r)
    if dados is not None:
        return extrair_registros_json(dados, r.url), r.url, ""
    registros = extrair_registros_html(html, r.url)
    if registros:
        return registros, r.url, html
    for link in links_para_contratos(html, r.url):
        if link == r.url:
            continue
        try:
            r2 = _get(sessao, link)
        except requests.RequestException:
            continue
        dados = _resposta_json(r2)
        regs = extrair_registros_json(dados, r2.url) if dados is not None else extrair_registros_html(r2.text, r2.url)
        if regs:
            return regs, r2.url, html + r2.text
    if _parece_spa(html):
        raise AcessoManual("Portal dinâmico (JavaScript): a consulta de contratos exige navegação no navegador.")
    raise AcessoManual("Portal respondeu, mas a listagem de contratos não está em HTML estático "
                       "(exige filtros/formulário). Consulte pelo link direto.")


def coletar_generico(sessao, mun: dict, ini: date, fim: date):
    alvo = mun.get("url_contratos") or mun["url"]
    try:
        return _coletar_html(sessao, alvo, mun)
    except requests.HTTPError as exc:
        if alvo != mun["url"] and exc.response is not None and exc.response.status_code == 404:
            return _coletar_html(sessao, mun["url"], mun)
        raise


TIMEOUT_EXPORTACAO = (6, 120)

# Campos do export JSON da tela "Contratos" do Fiorilli SCPI (InformacoesContratos.ASPX).
_CAMPOS_FIORILLI = {
    "numero": ("CODIGO", "CONTRATONUM"),
    "data_assinatura": ("DATAASSINATURA", "DTASSINATURA", "VIGENI"),
    "contratada": ("FORNECEDOR", "NOMEFOR"),
    "cnpj": ("INSMF", "CNPJ", "CPFCNPJ"),
    "valor": ("VALCON", "VALOR", "VALORCONTRATO"),
    "objeto": ("OBJETO_COMPLETO", "OBJETO", "OBJETOCONTRATO"),
}


def _registro_fiorilli(item: dict) -> dict:
    reg: dict = {"_links": {}}
    for campo, chaves in _CAMPOS_FIORILLI.items():
        reg[campo] = next((item[k] for k in chaves if item.get(k) not in (None, "")), None)
    ini_v, fim_v = parse_data(item.get("VIGENI")), parse_data(item.get("VENCIMENTO_ATUAL") or item.get("VIGENF"))
    if ini_v or fim_v:
        reg["vigencia"] = " a ".join(d.strftime("%d/%m/%Y") for d in (ini_v, fim_v) if d)
    return reg


def _form_postback(html: str, botao: str) -> dict:
    """Monta os campos de um postback ASP.NET simulando o clique num <input type=image>."""
    from bs4 import BeautifulSoup
    form = BeautifulSoup(html, "lxml").find("form")
    if form is None:
        raise AcessoManual("Tela de contratos do Fiorilli sem formulário reconhecível.")
    dados = {}
    for i in form.find_all("input"):
        if i.get("name") and i.get("type") not in ("image", "submit", "button", "checkbox", "radio"):
            dados[i["name"]] = i.get("value", "")
    dados[f"{botao}.x"], dados[f"{botao}.y"] = "10", "10"
    return dados


def coletar_fiorilli(sessao, mun: dict, ini: date, fim: date):
    """Fiorilli SCPI 9.0 (ASP.NET/DevExpress).

    Fluxo real do portal: (1) abre a página inicial para criar a sessão (entidade e
    exercício padrão); (2) carrega ``InformacoesContratos.ASPX``; (3) aciona o botão
    "Exportar dados para .JSON", que devolve todos os contratos do exercício de uma vez
    (a grade da tela mostra só 24 por página).
    """
    raiz = P.raiz_fiorilli(mun["url"])
    _get(sessao, raiz)  # cria a sessão ASP.NET
    pagina = raiz + "InformacoesContratos.ASPX"
    r = _get(sessao, pagina)
    if "gridContratos" not in r.text:
        raise AcessoManual("Tela de contratos do Fiorilli não encontrada neste portal.")
    dados = _form_postback(r.text, "ASPxPageControl1$btnExportarJSON")
    r2 = sessao.post(pagina, data=dados, timeout=TIMEOUT_EXPORTACAO, verify=VERIFICAR_SSL)
    r2.raise_for_status()
    try:
        lista = json.loads(r2.content.decode("utf-8-sig"))
    except ValueError:
        # Exportação indisponível: lê a 1ª página da grade (24 contratos mais recentes).
        regs = extrair_registros_devexpress(r.text, raiz)
        if regs:
            return regs, raiz, r.text
        raise AcessoManual("O portal Fiorilli não liberou a exportação dos contratos.")
    if isinstance(lista, dict):
        lista = next((v for v in lista.values() if isinstance(v, list)), [])
    exercicio = ini.year
    regs = [_registro_fiorilli(i) for i in lista
            if isinstance(i, dict) and str(i.get("ANO", exercicio)) == str(exercicio)]
    return regs, raiz, r.text


def coletar_dinamico(sessao, mun: dict, ini: date, fim: date):
    """Portais SPA (Betha Cloud, Atende.net, Elotech): verifica disponibilidade."""
    _get(sessao, mun["url"])
    raise AcessoManual(f"Portal {mun.get('provedor')} é dinâmico (SPA/JavaScript). "
                       "Use o link direto para a consulta de contratos.")


def coletar_betha_egov(sessao, mun: dict, ini: date, fim: date):
    """Betha e-Gov (JSF): lê a listagem quando servida em HTML estático."""
    return _coletar_html(sessao, mun.get("url_contratos") or mun["url"], mun)


ROTEADOR: dict[str, Callable] = {
    P.FIORILLI: coletar_fiorilli,
    P.BETHA_CLOUD: coletar_dinamico,
    P.IPM_ATENDE: coletar_dinamico,
    P.ELOTECH: coletar_dinamico,
    P.BETHA_EGOV: coletar_betha_egov,
}


# --------------------------------------------------------------------------- #
# Normalização + filtros
# --------------------------------------------------------------------------- #
def _enriquecer_links(sessao, links: dict[str, str]) -> dict[str, str]:
    """Visita a página de detalhe do contrato para localizar OS e Empenho."""
    detalhe = links.get("detalhe") or (links.get("contrato") if links.get("contrato", "").lower().split("?")[0]
                                       .endswith((".htm", ".html", ".aspx", ".php", ".faces", ".jsp", "/")) else None)
    if not detalhe:
        return links
    try:
        r = _get(sessao, detalhe)
    except requests.RequestException:
        return links
    from bs4 import BeautifulSoup  # import local: só quando há detalhe
    novos = links_documentos(BeautifulSoup(r.text, "lxml"), r.url)
    for k, v in novos.items():
        links.setdefault(k, v)
    links.setdefault("contrato", detalhe)
    return links


def normalizar_registros(sessao, registros: Iterable[dict], mun: dict, url_consulta: str,
                         ini: date, fim: date, provedor: str) -> list[Contrato]:
    contratos: list[Contrato] = []
    detalhes = 0
    for reg in registros:
        objeto = str(reg.get("objeto") or "").strip()
        areas = classificar_areas(objeto)
        if not areas:
            continue
        dt = parse_data(reg.get("data_assinatura"))
        if dt is not None and not (ini <= dt <= fim):
            continue
        links = dict(reg.get("_links") or {})
        if detalhes < MAX_DETALHES and not (links.get("os") and links.get("empenho")):
            if links.get("detalhe") or links.get("contrato"):
                links = _enriquecer_links(sessao, links)
                detalhes += 1
        contratada = str(reg.get("contratada") or "").strip()
        cnpj = formatar_cnpj(reg.get("cnpj")) if reg.get("cnpj") else extrair_cnpj(contratada)
        contratos.append(Contrato(
            municipio=mun["municipio"],
            numero=str(reg.get("numero") or "s/nº").strip(),
            data_assinatura=dt,
            contratada=contratada,
            cnpj=cnpj,
            objeto=objeto,
            valor=parse_valor(reg.get("valor")),
            vigencia=str(reg.get("vigencia") or "").strip(),
            link_contrato=links.get("contrato"),
            link_os=links.get("os"),
            link_empenho=links.get("empenho"),
            link_portal=url_consulta or mun["url"],
            areas=areas,
            provedor=provedor,
        ))
    return contratos


# --------------------------------------------------------------------------- #
# API pública
# --------------------------------------------------------------------------- #
def coletar_municipio(mun: dict, ini: date, fim: date) -> dict:
    """Coleta um município. Retorna dict serializável {contratos, diagnostico}."""
    inicio = time.perf_counter()
    provedor = mun.get("provedor") or P.detectar_por_url(mun.get("url"))
    url_consulta = mun.get("url_contratos") or P.url_consulta_contratos(mun.get("url", ""), provedor)
    diag = Diagnostico(mun["municipio"], provedor, STATUS_MANUAL, "", mun.get("url", ""), url_consulta)
    contratos: list[Contrato] = []

    if not mun.get("url"):
        diag.mensagem = "URL do portal não informada na planilha."
        return {"contratos": [], "diagnostico": asdict(diag)}

    sessao = criar_sessao()
    try:
        if provedor == P.OUTRO:
            # Provedor não identificado pela URL: tenta pela assinatura do HTML
            # antes de rotear (ex.: Fiorilli SCPI hospedado em domínio próprio).
            try:
                provedor = P.detectar_por_html(_get(sessao, mun["url"]).text) or provedor
                diag.provedor = provedor
            except requests.RequestException:
                pass
        fn = ROTEADOR.get(provedor, coletar_generico)
        registros, url_lida, html = fn(sessao, mun, ini, fim)
        if provedor == P.OUTRO:
            provedor = P.detectar_por_html(html) or provedor
            diag.provedor = provedor
        diag.url_consulta = url_lida or url_consulta
        contratos = normalizar_registros(sessao, registros, mun, diag.url_consulta, ini, fim, provedor)
        diag.registros_lidos = len(registros)
        diag.contratos_tecnicos = len(contratos)
        diag.status = STATUS_ONLINE
        diag.mensagem = f"{len(registros)} registro(s) lidos; {len(contratos)} de Engenharia/Agronomia/Geociências no período."
    except AcessoManual as exc:
        diag.status, diag.mensagem = STATUS_MANUAL, str(exc)
    except requests.Timeout:
        diag.status, diag.mensagem = STATUS_INSTAVEL, f"Tempo de resposta excedido ({TIMEOUT[1]}s)."
    except requests.exceptions.SSLError:
        diag.status, diag.mensagem = STATUS_INSTAVEL, "Falha no certificado SSL do portal."
    except requests.ConnectionError:
        diag.status, diag.mensagem = STATUS_INSTAVEL, "Portal fora do ar ou recusando conexões."
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else 0
        if code >= 500:
            diag.status, diag.mensagem = STATUS_INSTAVEL, f"Erro no servidor do portal (HTTP {code})."
        else:
            diag.status, diag.mensagem = STATUS_MANUAL, f"Consulta bloqueada ou endereço alterado (HTTP {code})."
    except Exception as exc:  # nunca derruba a pesquisa da Área 1
        diag.status, diag.mensagem = STATUS_MANUAL, f"Layout não reconhecido: {type(exc).__name__}: {exc}"[:300]
    finally:
        sessao.close()
        diag.tempo_s = round(time.perf_counter() - inicio, 2)

    return {"contratos": [asdict(c) for c in contratos], "diagnostico": asdict(diag)}


def coletar(municipios: list[dict], ini: date, fim: date, *,
            fn_municipio: Callable[[dict, date, date], dict] = coletar_municipio,
            progress_cb: Callable[[int, int, dict], None] | None = None,
            initializer: Callable[[], None] | None = None,
            max_workers: int = MAX_WORKERS) -> tuple[list[dict], list[dict]]:
    """Coleta os municípios em paralelo. Retorna (contratos, diagnosticos)."""
    contratos: list[dict] = []
    diagnosticos: list[dict] = []
    total = len(municipios)
    if not total:
        return contratos, diagnosticos
    with ThreadPoolExecutor(max_workers=min(max_workers, total), initializer=initializer) as ex:
        futuros = {ex.submit(fn_municipio, m, ini, fim): m for m in municipios}
        for i, fut in enumerate(as_completed(futuros), 1):
            mun = futuros[fut]
            try:
                res = fut.result()
            except Exception as exc:
                res = {"contratos": [], "diagnostico": asdict(Diagnostico(
                    mun["municipio"], mun.get("provedor", ""), STATUS_INSTAVEL, str(exc)[:300],
                    mun.get("url", ""), mun.get("url_contratos", "")))}
            contratos.extend(res["contratos"])
            diagnosticos.append(res["diagnostico"])
            if progress_cb:
                progress_cb(i, total, res["diagnostico"])
    diagnosticos.sort(key=lambda d: d["municipio"])
    return contratos, diagnosticos
