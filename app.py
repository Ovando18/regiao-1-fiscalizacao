"""FiscalizaObras-MS | Área 1 — Painel de fiscalização de contratos (Crea-MS).

Coleta direta nos Portais da Transparência dos municípios da Área 1 (sem PNCP).
Execução local:  streamlit run app.py
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from config import EXERCICIO, carregar_municipios, ler_planilha
from scrapers.collector import (
    STATUS_INSTAVEL,
    STATUS_MANUAL,
    STATUS_ONLINE,
    coletar,
    coletar_municipio,
)
from scrapers.keywords import AREA_TODAS, AREAS_TECNICAS, normalizar
from utils.export_excel import gerar_xlsx
from utils.styles import (
    CORES_STATUS,
    CSS,
    cabecalho_html,
    kpi_html,
    moeda_br,
    secao_html,
    selo_sidebar_html,
)

st.set_page_config(
    page_title="FiscalizaObras-MS | Área 1",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CSS, unsafe_allow_html=True)

OPCAO_TODOS = "Todos os municípios da Área 1"
INICIO_EXERCICIO = date(EXERCICIO, 1, 1)
FIM_EXERCICIO = date(EXERCICIO, 12, 31)
HOJE = min(max(date.today(), INICIO_EXERCICIO), FIM_EXERCICIO)


# --------------------------------------------------------------------------- #
# Dados (com cache)
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def _municipios_da_raiz() -> tuple[list[dict], str, list[str]]:
    return carregar_municipios()


@st.cache_data(show_spinner=False)
def _municipios_do_upload(conteudo: bytes) -> tuple[list[dict], list[str]]:
    return ler_planilha(conteudo)


@st.cache_data(ttl=3600, show_spinner=False, max_entries=500)
def coletar_municipio_cache(municipio: str, url: str, provedor: str, url_contratos: str,
                            ini: date, fim: date) -> dict:
    """Cache por município + período (1 h): repetir a pesquisa não reconsulta o portal."""
    mun = {"municipio": municipio, "url": url, "provedor": provedor, "url_contratos": url_contratos}
    return coletar_municipio(mun, ini, fim)


def _fn_cache(mun: dict, ini: date, fim: date) -> dict:
    return coletar_municipio_cache(mun["municipio"], mun.get("url", ""), mun.get("provedor", ""),
                                   mun.get("url_contratos", ""), ini, fim)


def _inicializador_threads():
    """Propaga o contexto do Streamlit para as threads (necessário ao st.cache_data)."""
    try:
        from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
        ctx = get_script_run_ctx()
    except Exception:
        return None

    def _init():
        import threading
        if ctx is not None:
            add_script_run_ctx(threading.current_thread(), ctx)
    return _init


def montar_dataframe(contratos: list[dict]) -> pd.DataFrame:
    colunas = ["Município", "Nº Contrato", "Data Assinatura", "Contratada", "CNPJ", "Empresa Contratada (CNPJ/Nome)",
               "Objeto", "Valor (R$)", "Vigência", "Área Técnica", "📄 Contrato", "📋 Ordem de Serviço",
               "💰 Empenho", "🌐 Portal", "Docs", "Provedor", "_areas"]
    if not contratos:
        return pd.DataFrame(columns=colunas)
    linhas = []
    for c in contratos:
        empresa = " — ".join(x for x in (c.get("cnpj"), c.get("contratada")) if x) or "Não informado"
        linhas.append({
            "Município": c["municipio"],
            "Nº Contrato": c["numero"],
            "Data Assinatura": c["data_assinatura"],
            "Contratada": c.get("contratada") or "",
            "CNPJ": c.get("cnpj") or "",
            "Empresa Contratada (CNPJ/Nome)": empresa,
            "Objeto": c["objeto"],
            "Valor (R$)": c.get("valor"),
            "Vigência": c.get("vigencia") or "",
            "Área Técnica": ", ".join(c.get("areas") or []),
            "📄 Contrato": c.get("link_contrato"),
            "📋 Ordem de Serviço": c.get("link_os"),
            "💰 Empenho": c.get("link_empenho"),
            "🌐 Portal": c.get("link_portal"),
            "Docs": sum(bool(c.get(k)) for k in ("link_contrato", "link_os", "link_empenho")),
            "Provedor": c.get("provedor", ""),
            "_areas": c.get("areas") or [],
        })
    df = pd.DataFrame(linhas, columns=colunas)
    df["Data Assinatura"] = pd.to_datetime(df["Data Assinatura"], errors="coerce")
    df["Valor (R$)"] = pd.to_numeric(df["Valor (R$)"], errors="coerce")
    return df.sort_values(["Data Assinatura", "Município"], ascending=[False, True], na_position="last").reset_index(drop=True)


def aplicar_filtros(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    if df.empty:
        return df
    m = pd.Series(True, index=df.index)
    datas = df["Data Assinatura"]
    m &= datas.isna() | ((datas.dt.date >= f["ini"]) & (datas.dt.date <= f["fim"]))
    if f["area"] != AREA_TODAS:
        m &= df["_areas"].apply(lambda a: f["area"] in a)
    if f["texto"]:
        termo = normalizar(f["texto"])
        digitos = "".join(ch for ch in f["texto"] if ch.isdigit())
        alvo = (df["Objeto"] + " " + df["Nº Contrato"].astype(str) + " " + df["Contratada"] + " " + df["CNPJ"]).map(normalizar)
        cond = alvo.str.contains(termo, regex=False)
        if len(digitos) >= 5:
            cond |= df["CNPJ"].str.replace(r"\D", "", regex=True).str.contains(digitos, regex=False)
        m &= cond
    valores = df["Valor (R$)"]
    if f["vmin"] > 0:
        m &= valores.fillna(0) >= f["vmin"]
    if f["vmax"] > 0:
        m &= valores.fillna(0) <= f["vmax"]
    if f["docs_completos"]:
        m &= df["Docs"].eq(3)
    return df[m].reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Municípios da Área 1
# --------------------------------------------------------------------------- #
municipios, fonte_municipios, avisos_planilha = _municipios_da_raiz()
upload = st.session_state.get("planilha_upload")
if upload is not None:
    mu, av = _municipios_do_upload(upload)
    if mu:
        municipios, fonte_municipios, avisos_planilha = mu, "Planilha enviada pelo painel", av
nomes_municipios = [m["municipio"] for m in municipios]
por_nome = {m["municipio"]: m for m in municipios}

# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown(selo_sidebar_html(), unsafe_allow_html=True)

    st.markdown("**Municípios da Área 1**")
    todos = st.toggle(OPCAO_TODOS, value=True, disabled=not municipios)
    selecionados = st.multiselect(
        "Selecionar municípios", nomes_municipios, default=[], disabled=todos or not municipios,
        placeholder="Escolha um ou mais municípios", label_visibility="collapsed",
    )
    alvo = nomes_municipios if todos else selecionados

    st.markdown("**Período de assinatura**")
    data_ini = st.date_input("Data Inicial", value=INICIO_EXERCICIO, min_value=INICIO_EXERCICIO,
                             max_value=FIM_EXERCICIO, format="DD/MM/YYYY")
    data_fim = st.date_input("Data Final", value=HOJE, min_value=INICIO_EXERCICIO,
                             max_value=FIM_EXERCICIO, format="DD/MM/YYYY")

    st.markdown("**Filtros de auditoria**")
    area = st.selectbox("Área Técnica", [AREA_TODAS, *AREAS_TECNICAS.keys()])
    texto = st.text_input("Busca livre", placeholder="Objeto, nº do contrato, CNPJ ou empresa")
    v1, v2 = st.columns(2)
    vmin = v1.number_input("Valor mín. (R$)", min_value=0.0, value=0.0, step=10000.0, format="%.2f")
    vmax = v2.number_input("Valor máx. (R$)", min_value=0.0, value=0.0, step=10000.0, format="%.2f",
                           help="0 = sem limite")
    docs_completos = st.checkbox("Somente documentação completa (Contrato + OS + Empenho)")

    st.write("")
    pesquisar = st.button("🔎 Pesquisar Contratos (Área 1)", type="primary", use_container_width=True,
                          disabled=not alvo)
    limpar = st.button("↻ Atualizar / Limpar Cache", use_container_width=True)

    with st.expander("Planilha da Área 1"):
        st.caption(f"Fonte atual: **{fonte_municipios}** · {len(municipios)} município(s)")
        arquivo = st.file_uploader("Enviar planilha .xlsx atualizada", type=["xlsx"])
        if arquivo is not None and st.session_state.get("planilha_upload") != arquivo.getvalue():
            st.session_state["planilha_upload"] = arquivo.getvalue()
            st.session_state.pop("resultado", None)
            st.rerun()
        for a in avisos_planilha:
            st.caption(f"⚠️ {a}")

if limpar:
    st.cache_data.clear()
    for k in ("resultado", "planilha_upload"):
        st.session_state.pop(k, None)
    st.toast("Cache limpo. A próxima pesquisa consultará os portais novamente.", icon="✅")
    st.rerun()

# --------------------------------------------------------------------------- #
# Cabeçalho
# --------------------------------------------------------------------------- #
st.markdown(cabecalho_html(nomes_municipios, EXERCICIO), unsafe_allow_html=True)

if not municipios:
    st.markdown(
        '<div class="fo-aviso"><b>Planilha da Área 1 não encontrada.</b> Coloque o arquivo <code>.xlsx</code> '
        "com as colunas <i>Município</i> e <i>URL do Portal da Transparência</i> na raiz do projeto "
        "(e rode <code>python scripts/gerar_config_area1.py</code>) ou envie a planilha pela barra lateral "
        "em <b>Planilha da Área 1</b>.</div>", unsafe_allow_html=True)
    st.stop()

if data_ini > data_fim:
    st.error("A Data Inicial não pode ser posterior à Data Final.")
    st.stop()

# --------------------------------------------------------------------------- #
# Pesquisa
# --------------------------------------------------------------------------- #
if pesquisar:
    lista = [por_nome[n] for n in alvo]
    with st.status(f"Consultando {len(lista)} portal(is) da Área 1…", expanded=True) as status:
        barra = st.progress(0.0, text="Iniciando consultas paralelas…")
        log = st.empty()
        linhas_log: list[str] = []

        def _progresso(i: int, total: int, diag: dict) -> None:
            icone = {"Online": "🟢", "Instável / Timeout": "🟡"}.get(diag["status"], "🔵")
            linhas_log.append(f"{icone} **{diag['municipio']}** — {diag['status']} ({diag['tempo_s']}s)")
            barra.progress(i / total, text=f"{i}/{total} portais consultados")
            log.markdown("  \n".join(linhas_log[-8:]))

        contratos, diagnosticos = coletar(lista, data_ini, data_fim, fn_municipio=_fn_cache,
                                          progress_cb=_progresso, initializer=_inicializador_threads())
        online = sum(d["status"] == STATUS_ONLINE for d in diagnosticos)
        status.update(label=f"Pesquisa concluída: {len(contratos)} contrato(s) técnico(s) · "
                            f"{online}/{len(diagnosticos)} portais online", state="complete", expanded=False)
    st.session_state["resultado"] = {
        "contratos": contratos, "diagnosticos": diagnosticos,
        "ini": data_ini, "fim": data_fim, "municipios": alvo,
    }

resultado = st.session_state.get("resultado")
if not resultado:
    st.markdown(
        f'<div class="fo-card fo-vazio">Selecione os municípios e o período na barra lateral e clique em '
        f'<b>Pesquisar Contratos (Área 1)</b>.<br><small>{len(municipios)} município(s) da Área 1 carregados '
        f'a partir de: {fonte_municipios}</small></div>', unsafe_allow_html=True)
    st.stop()

filtros = {"ini": data_ini, "fim": data_fim, "area": area, "texto": texto.strip(),
           "vmin": vmin, "vmax": vmax, "docs_completos": docs_completos}
df_total = montar_dataframe(resultado["contratos"])
df = aplicar_filtros(df_total, filtros)
diags = resultado["diagnosticos"]

if (resultado["ini"], resultado["fim"]) != (data_ini, data_fim):
    st.info(f"Os dados exibidos foram coletados para {resultado['ini']:%d/%m/%Y} a {resultado['fim']:%d/%m/%Y}. "
            "Clique em Pesquisar para consultar os portais no novo período.", icon="ℹ️")

# --------------------------------------------------------------------------- #
# KPIs
# --------------------------------------------------------------------------- #
total_valor = float(df["Valor (R$)"].sum(skipna=True)) if len(df) else 0.0
n_online = sum(d["status"] == STATUS_ONLINE for d in diags)
taxa_docs = (df["Docs"].sum() / (3 * len(df)) * 100) if len(df) else 0.0
k1, k2, k3, k4 = st.columns(4)
k1.markdown(kpi_html("Contratos encontrados", f"{len(df):,}".replace(",", "."),
                     f"de {len(df_total)} coletados antes dos filtros"), unsafe_allow_html=True)
k2.markdown(kpi_html("Valor global contratado", moeda_br(total_valor),
                     f"{df['Valor (R$)'].notna().sum()} contrato(s) com valor informado", "verde"),
            unsafe_allow_html=True)
k3.markdown(kpi_html("Municípios consultados", str(len(diags)),
                     f"{n_online} online · {len(diags) - n_online} com pendência"), unsafe_allow_html=True)
k4.markdown(kpi_html("Documentação localizada", f"{taxa_docs:.1f}%",
                     f"{int(df['Docs'].eq(3).sum()) if len(df) else 0} contrato(s) com os 3 documentos",
                     "amarelo"), unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Tabela de contratos
# --------------------------------------------------------------------------- #
st.markdown(secao_html("Contratos de Engenharia, Agronomia e Geociências"), unsafe_allow_html=True)
colunas_tabela = ["Município", "Nº Contrato", "Data Assinatura", "Empresa Contratada (CNPJ/Nome)", "Objeto",
                  "Valor (R$)", "Vigência", "📄 Contrato", "📋 Ordem de Serviço", "💰 Empenho", "🌐 Portal"]
if df.empty:
    st.markdown('<div class="fo-card fo-vazio">Nenhum contrato encontrado com os filtros atuais. '
                'Verifique o <b>Diagnóstico dos Portais</b> abaixo: portais com <i>Acesso Manual</i> '
                'devem ser consultados pelo link direto.</div>', unsafe_allow_html=True)
else:
    tabela = df[colunas_tabela].copy()
    tabela["Valor (R$)"] = tabela["Valor (R$)"].map(moeda_br)
    st.dataframe(
        tabela, hide_index=True, use_container_width=True, height=min(560, 42 + 35 * len(tabela)),
        column_config={
            "Data Assinatura": st.column_config.DateColumn(format="DD/MM/YYYY", width="small"),
            "Nº Contrato": st.column_config.TextColumn(width="small"),
            "Objeto": st.column_config.TextColumn(width="large"),
            "Empresa Contratada (CNPJ/Nome)": st.column_config.TextColumn(width="medium"),
            "📄 Contrato": st.column_config.LinkColumn("📄 Contrato Celebrado", display_text="Abrir contrato",
                                                     help="Vazio = não disponibilizado no portal"),
            "📋 Ordem de Serviço": st.column_config.LinkColumn("📋 Ordem de Serviço (OS)", display_text="Abrir OS",
                                                             help="Vazio = OS não disponibilizada no portal"),
            "💰 Empenho": st.column_config.LinkColumn("💰 Empenho / Pagamentos", display_text="Abrir empenho",
                                                    help="Vazio = empenho não localizado no portal"),
            "🌐 Portal": st.column_config.LinkColumn("🌐 Portal Municipal", display_text="Abrir portal"),
        },
    )

    # Exportação
    e1, e2 = st.columns([1, 3])
    e1.download_button(
        "⬇️ Exportar Planilha (.xlsx)",
        data=gerar_xlsx(df, (resultado["ini"], resultado["fim"]), EXERCICIO),
        file_name=f"FiscalizaObras_Area1_{EXERCICIO}_{date.today():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary", use_container_width=True,
    )
    e2.caption("Aba 1: contratos filtrados com hiperlinks · Aba 2: resumo consolidado por município da Área 1.")

    # ----------------------------------------------------------------------- #
    # Ficha de fiscalização
    # ----------------------------------------------------------------------- #
    st.markdown(secao_html("Ficha Detalhada de Fiscalização"), unsafe_allow_html=True)

    def _rotulo(i: int) -> str:
        r = df.iloc[i]
        d = r["Data Assinatura"].strftime("%d/%m/%Y") if pd.notna(r["Data Assinatura"]) else "s/ data"
        return f"{r['Município']} · Contrato {r['Nº Contrato']} · {d} · {str(r['Objeto'])[:80]}"

    idx = st.selectbox("Selecione um contrato da listagem", range(len(df)), format_func=_rotulo)
    c = df.iloc[idx]
    from html import escape as _e
    data_txt = c["Data Assinatura"].strftime("%d/%m/%Y") if pd.notna(c["Data Assinatura"]) else "Não informada"
    tags = "".join(f'<span class="fo-tag">{_e(a)}</span>' for a in c["_areas"])
    st.markdown(f"""
<div class="fo-card">
  <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-start">
    <div><div style="font-size:.75rem;color:#5B6B7F;font-weight:700;letter-spacing:.05em">FICHA DE FISCALIZAÇÃO • ÁREA 1</div>
      <div style="font-size:1.25rem;font-weight:800;color:#004B87">Contrato nº {_e(str(c['Nº Contrato']))} — {_e(c['Município'])}</div></div>
    <div>{tags}</div>
  </div>
  <div class="fo-objeto"><b>Objeto:</b> {_e(str(c['Objeto']))}</div>
  <div class="fo-ficha-grid" style="margin-top:12px">
    <div><div class="rot">Empresa contratada</div><div class="val">{_e(c['Contratada'] or 'Não informada')}</div></div>
    <div><div class="rot">CNPJ</div><div class="val">{_e(c['CNPJ'] or 'Não informado')}</div></div>
    <div><div class="rot">Data de assinatura</div><div class="val">{data_txt}</div></div>
    <div><div class="rot">Vigência</div><div class="val">{_e(c['Vigência'] or 'Não informada')}</div></div>
    <div><div class="rot">Valor contratado</div><div class="val">{moeda_br(c['Valor (R$)'] if pd.notna(c['Valor (R$)']) else None)}</div></div>
    <div><div class="rot">Documentos localizados</div><div class="val">{int(c['Docs'])} de 3</div></div>
    <div><div class="rot">Provedor do portal</div><div class="val">{_e(c['Provedor'] or '—')}</div></div>
  </div>
</div>""", unsafe_allow_html=True)
    st.write("")
    b1, b2, b3, b4 = st.columns(4)
    for col, chave, rotulo in ((b1, "📄 Contrato", "📄 Abrir / Baixar Contrato"),
                               (b2, "📋 Ordem de Serviço", "📋 Abrir / Baixar Ordem de Serviço"),
                               (b3, "💰 Empenho", "💰 Abrir Empenho / Pagamentos")):
        link = c[chave]
        if isinstance(link, str) and link:
            col.link_button(rotulo, link, type="primary", use_container_width=True)
        else:
            col.button(f"{rotulo.split(' ', 1)[0]} Não disponibilizado no portal", disabled=True,
                       use_container_width=True, key=f"nd_{chave}")
    b4.link_button("🌐 Portal Municipal", c["🌐 Portal"] or por_nome.get(c["Município"], {}).get("url", ""),
                   use_container_width=True)

# --------------------------------------------------------------------------- #
# Diagnóstico dos portais
# --------------------------------------------------------------------------- #
st.markdown(secao_html("Diagnóstico dos Portais da Área 1"), unsafe_allow_html=True)
contagem = {s: sum(d["status"] == s for d in diags) for s in (STATUS_ONLINE, STATUS_INSTAVEL, STATUS_MANUAL)}
resumo_status = " &nbsp;&nbsp; ".join(
    f'<span class="fo-status"><i style="background:{CORES_STATUS[s]}"></i>{s}: {n}</span>' for s, n in contagem.items())
with st.expander(f"Status de resposta de {len(diags)} prefeitura(s) — {contagem[STATUS_ONLINE]} online",
                 expanded=contagem[STATUS_ONLINE] < len(diags)):
    st.markdown(resumo_status, unsafe_allow_html=True)
    ddf = pd.DataFrame(diags)
    if not ddf.empty:
        ddf["status"] = ddf["status"].map(lambda s: {"Online": "🟢 ", "Instável / Timeout": "🟡 "}.get(s, "🔵 ") + s)
        st.dataframe(
            ddf[["municipio", "status", "provedor", "contratos_tecnicos", "tempo_s", "mensagem",
                 "url_consulta", "url_portal"]],
            hide_index=True, use_container_width=True,
            column_config={
                "municipio": "Município", "status": "Status", "provedor": "Provedor",
                "contratos_tecnicos": st.column_config.NumberColumn("Contratos técnicos", width="small"),
                "tempo_s": st.column_config.NumberColumn("Tempo (s)", format="%.1f", width="small"),
                "mensagem": st.column_config.TextColumn("Diagnóstico", width="large"),
                "url_consulta": st.column_config.LinkColumn("Consulta de contratos", display_text="Abrir consulta"),
                "url_portal": st.column_config.LinkColumn("Portal", display_text="Abrir portal"),
            },
        )
    st.caption("🔵 Acesso Manual: o portal exige navegação dinâmica (JavaScript/formulários) ou bloqueou a consulta "
               "automática — use o link direto. 🟡 Instável/Timeout: tente novamente com “Atualizar / Limpar Cache”.")

st.markdown('<div class="fo-rodape">FiscalizaObras-MS • Área 1 de Fiscalização de Obras e Serviços Técnicos — Crea-MS • '
            'Dados obtidos diretamente dos Portais da Transparência municipais (Lei nº 12.527/2011). '
            'Confira sempre o documento original no portal antes de lavrar autos.</div>', unsafe_allow_html=True)
