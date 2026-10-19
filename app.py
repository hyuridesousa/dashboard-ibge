
"""
Painel Analítico Interativo — Taxa de Desocupação por UF (PNAD Contínua / IBGE)

Atende aos requisitos de visões coordenadas (Multiple Coordinated Views):
  1. Mapa coroplético (Visão Geral Espacial)
  2. Ranking de barras ordenadas (Distribuição Categórica)
  3. Série histórica temporal (Visão Geral Temporal)
  4. Painel de detalhes + Tabela filtrada (Details-on-Demand)

Aplica o mantra de Shneiderman e regras de acessibilidade e Data-Ink Ratio.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(
    page_title="Desocupação por UF — PNAD Contínua",
    page_icon="📊",
    layout="wide",
)

# --------------------------------------------------------------------------
# Constantes e Configurações Visuais
# --------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"
SIDRA_URL = "https://apisidra.ibge.gov.br/values/t/4099/n3/all/v/4099/p/all"
GEO_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&intradivision=UF"
GEO_FALLBACK = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

UF_SIGLA = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}
REGIOES = {"1": "Norte", "2": "Nordeste", "3": "Sudeste", "4": "Sul", "5": "Centro-Oeste"}

# Paleta Okabe-Ito (Segura para daltonismo) + tons neutros
AZUL, LARANJA, VERDE, ROSA, CELESTE, VERMELHAO, PRETO = (
    "#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#222222",
)
CORES_SELECAO = [AZUL, LARANJA, VERDE, ROSA, CELESTE, VERMELHAO, PRETO]
CINZA_CONTEXTO = "#B8B8B8"
CINZA_NAO_SELECIONADO = "#CFCFCF"
ESCALA_SEQUENCIAL = "Cividis"
MAX_UFS_COLORIDAS = len(CORES_SELECAO)


# --------------------------------------------------------------------------
# Funções de Leitura e Tratamento de Dados
# --------------------------------------------------------------------------
def _num(x: float, sinal: bool = False) -> str:
    if pd.isna(x):
        return "—"
    txt = f"{x:+.1f}" if sinal else f"{x:.1f}"
    return txt.replace(".", ",")


@st.cache_data(ttl=86400, show_spinner="Carregando dados da PNAD Contínua…")
def carregar_dados() -> pd.DataFrame:
    csv_local = DATA_DIR / "pnad_4099.csv"
    if csv_local.exists():
        df = pd.read_csv(csv_local, dtype={"uf_code": str, "periodo": str})
    else:
        resp = requests.get(SIDRA_URL, headers=HEADERS, timeout=90)
        resp.raise_for_status()
        linhas = resp.json()[1:]
        df = pd.DataFrame(
            {
                "uf_code": [x["D1C"] for x in linhas],
                "uf": [x["D1N"] for x in linhas],
                "periodo": [x["D3C"] for x in linhas],
                "taxa": [x["V"] for x in linhas],
            }
        )

    df["taxa"] = pd.to_numeric(df["taxa"], errors="coerce")
    df = df.dropna(subset=["taxa"]).copy()
    df["sigla"] = df["uf_code"].map(UF_SIGLA)
    df["regiao"] = df["uf_code"].str[0].map(REGIOES)
    df["ano"] = df["periodo"].str[:4].astype(int)
    df["tri"] = df["periodo"].str[4:].astype(int)
    df["data"] = pd.to_datetime(
        {"year": df["ano"], "month": (df["tri"] - 1) * 3 + 1, "day": 1}
    )
    df["rotulo"] = df["tri"].astype(str) + "ºT/" + df["ano"].astype(str)

    df = df.sort_values(["uf_code", "periodo"]).reset_index(drop=True)
    g = df.groupby("uf_code")["taxa"]
    df["var_tri"] = g.diff(1)
    df["var_ano"] = g.diff(4)
    df["posicao"] = (
        df.groupby("periodo")["taxa"].rank(ascending=False, method="min").astype(int)
    )
    df["n_ufs"] = df.groupby("periodo")["taxa"].transform("count")
    return df


@st.cache_data(ttl=604800, show_spinner="Carregando malha territorial do Brasil…")
def carregar_geojson() -> dict:
    arq = DATA_DIR / "uf.geojson"
    if arq.exists():
        gj = json.loads(arq.read_text(encoding="utf-8"))
    else:
        try:
            resp = requests.get(GEO_URL, headers=HEADERS, timeout=90)
            resp.raise_for_status()
            gj = resp.json()
        except Exception:
            resp = requests.get(GEO_FALLBACK, headers=HEADERS, timeout=90)
            resp.raise_for_status()
            gj = resp.json()

    SIGLA_TO_CODE = {
        "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16",
        "TO": "17", "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25",
        "PE": "26", "AL": "27", "SE": "28", "BA": "29", "MG": "31", "ES": "32",
        "RJ": "33", "SP": "35", "PR": "41", "SC": "42", "RS": "43", "MS": "50",
        "MT": "51", "GO": "52", "DF": "53"
    }

    for feat in gj.get("features", []):
        props = feat.setdefault("properties", {})
        sigla = props.get("sigla") or props.get("postal")
        codigo = props.get("codarea") or props.get("CD_UF") or props.get("id") or props.get("uf_code") or feat.get("id")
        if not codigo and sigla in SIGLA_TO_CODE:
            codigo = SIGLA_TO_CODE[sigla]
        props["uf_code"] = str(codigo) if codigo else ""
    return gj


def montar_customdata(d: pd.DataFrame) -> np.ndarray:
    return np.column_stack(
        [
            d["uf_code"].astype(str),
            d["uf"],
            d["sigla"],
            d["taxa"].map(_num),
            d["var_tri"].map(lambda v: _num(v, True)),
            d["var_ano"].map(lambda v: _num(v, True)),
            d["posicao"].astype(str) + "º de " + d["n_ufs"].astype(str),
            d["regiao"],
            d["rotulo"],
            d["periodo"].astype(str),
        ]
    )


TOOLTIP_PADRAO = (
    "<b>%{customdata[1]} (%{customdata[2]})</b> · Região %{customdata[7]}<br>"
    "Período: <b>%{customdata[8]}</b><br>"
    "Taxa de desocupação: <b>%{customdata[3]}%</b><br>"
    "Var. vs. trimestre anterior: <b>%{customdata[4]} p.p.</b><br>"
    "Var. vs. 12 meses antes: <b>%{customdata[5]} p.p.</b><br>"
    "Posição no ranking nacional: <b>%{customdata[6]}</b>"
    "<extra></extra>"
)

LAYOUT_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(size=12, color="#222222"),
    margin=dict(l=0, r=0, t=8, b=0),
    hoverlabel=dict(font_size=13, bgcolor="#FFFFFF"),
)


# --------------------------------------------------------------------------
# Captura de Seleções (Brushing & Linking via Session State)
# --------------------------------------------------------------------------
def pontos_selecionados(chave: str) -> list:
    estado = st.session_state.get(chave)
    try:
        return list(estado["selection"]["points"])
    except Exception:
        return []


def _primeiro_valor(v):
    if isinstance(v, (list, tuple)):
        return v[0] if len(v) > 0 else None
    return v


def ufs_da_selecao(chave: str, validos: set, fallback_key: str | None = None) -> set:
    ufs = set()
    for p in pontos_selecionados(chave):
        codigo = _primeiro_valor(p.get("customdata"))
        if codigo is None and fallback_key:
            codigo = p.get(fallback_key)
        if codigo is not None and str(codigo) in validos:
            ufs.add(str(codigo))
    return ufs


def periodos_da_selecao(chave: str, validos: set) -> set:
    periodos = set()
    for p in pontos_selecionados(chave):
        cd = p.get("customdata")
        per = cd[9] if isinstance(cd, (list, tuple)) and len(cd) > 9 else None
        if per is None and p.get("x"):
            d = pd.to_datetime(p["x"])
            per = f"{d.year}{(d.month - 1) // 3 + 1:02d}"
        if per is not None and str(per) in validos:
            periodos.add(str(per))
    return periodos


# --------------------------------------------------------------------------
# Componentes Gráficos (Plotly Figures)
# --------------------------------------------------------------------------
def fig_mapa(d: pd.DataFrame, geo: dict, ufs_sel: set) -> go.Figure:
    d = d.reset_index(drop=True)
    idx = [i for i, u in enumerate(d["uf_code"]) if u in ufs_sel] if ufs_sel else None
    fig = go.Figure(
        go.Choropleth(
            geojson=geo,
            featureidkey="properties.uf_code",
            locations=d["uf_code"],
            z=d["taxa"],
            customdata=montar_customdata(d),
            colorscale=ESCALA_SEQUENCIAL,
            marker_line_color="#FFFFFF",
            marker_line_width=0.8,
            colorbar=dict(
                title=dict(text="Desocupação (%)", side="top"),
                thickness=12, len=0.85, outlinewidth=0, ticksuffix="%",
            ),
            hovertemplate=TOOLTIP_PADRAO,
            selectedpoints=idx,
            selected=dict(marker=dict(opacity=1)),
            unselected=dict(marker=dict(opacity=0.25)),
        )
    )
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(**LAYOUT_BASE, height=420, clickmode="event+select")
    return fig


def fig_barras(d: pd.DataFrame, ufs_sel: set) -> go.Figure:
    d = d.sort_values("taxa", ascending=True).reset_index(drop=True)
    if ufs_sel:
        cores = [AZUL if u in ufs_sel else CINZA_NAO_SELECIONADO for u in d["uf_code"]]
    else:
        cores = AZUL
    fig = go.Figure(
        go.Bar(
            x=d["taxa"],
            y=d["uf"],
            orientation="h",
            marker=dict(color=cores),
            text=d["taxa"].map(_num),
            textposition="outside",
            cliponaxis=False,
            customdata=montar_customdata(d),
            hovertemplate=TOOLTIP_PADRAO,
        )
    )
    fig.update_xaxes(visible=False, range=[0, d["taxa"].max() * 1.15])
    fig.update_yaxes(showgrid=False, ticks="", tickfont=dict(size=12))
    fig.update_layout(
        **{**LAYOUT_BASE, "margin": dict(l=0, r=35, t=8, b=0)},
        height=max(420, 20 * len(d) + 30),
        bargap=0.25,
        dragmode="select",
        selectdirection="v",
        clickmode="event+select",
    )
    return fig


def fig_serie(
    dv: pd.DataFrame, ufs_sel: set, periodos_sel: set, ref_data: pd.Timestamp
) -> go.Figure:
    fig = go.Figure()
    
    for _, g in dv.groupby("uf_code"):
        fig.add_trace(
            go.Scatter(
                x=g["data"], y=g["taxa"], mode="lines",
                line=dict(color=CINZA_CONTEXTO, width=1),
                opacity=0.35 if ufs_sel else 0.65,
                hoverinfo="skip", showlegend=False,
            )
        )

    def obter_indices_selecionados(traco_df: pd.DataFrame):
        if not periodos_sel:
            return None
        return [i for i, p in enumerate(traco_df["periodo"]) if p in periodos_sel]

    if ufs_sel:
        ordem = sorted(ufs_sel, key=lambda u: UF_SIGLA.get(u, u))[:MAX_UFS_COLORIDAS]
        for i, uf in enumerate(ordem):
            g = dv[dv["uf_code"] == uf].sort_values("data")
            if g.empty:
                continue
            cor = CORES_SELECAO[i]
            fig.add_trace(
                go.Scatter(
                    x=g["data"], y=g["taxa"], mode="lines+markers",
                    line=dict(color=cor, width=2.5), marker=dict(color=cor, size=5),
                    customdata=montar_customdata(g), hovertemplate=TOOLTIP_PADRAO, showlegend=False,
                    selectedpoints=obter_indices_selecionados(g),
                    selected=dict(marker=dict(size=9, opacity=1)),
                    unselected=dict(marker=dict(opacity=0.3)),
                )
            )
            ultimo = g.iloc[-1]
            fig.add_annotation(
                x=ultimo["data"], y=ultimo["taxa"], text=f"<b>{ultimo['sigla']}</b>",
                showarrow=False, xanchor="left", xshift=6, font=dict(color=cor, size=12),
            )
    else:
        med = (
            dv.groupby(["periodo", "data", "rotulo"], as_index=False)["taxa"]
            .median()
            .sort_values("data")
        )
        cd = np.column_stack([med["periodo"]] * 10)
        cd[:, 8] = med["rotulo"]
        cd[:, 3] = med["taxa"].map(_num)
        fig.add_trace(
            go.Scatter(
                x=med["data"], y=med["taxa"], mode="lines+markers",
                line=dict(color=AZUL, width=2.5), marker=dict(color=AZUL, size=5),
                customdata=cd,
                hovertemplate=(
                    "<b>%{customdata[8]}</b><br>"
                    "Mediana das UFs exibidas: <b>%{customdata[3]}%</b><extra></extra>"
                ),
                showlegend=False,
                selectedpoints=obter_indices_selecionados(med),
                selected=dict(marker=dict(size=9, opacity=1)),
                unselected=dict(marker=dict(opacity=0.3)),
            )
        )
        fig.add_annotation(
            x=med.iloc[-1]["data"], y=med.iloc[-1]["taxa"], text="<b>Mediana</b>",
            showarrow=False, xanchor="left", xshift=6, font=dict(color=AZUL, size=12),
        )

    fig.add_shape(
        type="line", x0=ref_data, x1=ref_data, yref="paper", y0=0, y1=1,
        line=dict(color="#555555", width=1.2, dash="dot"),
    )
    fig.update_xaxes(showgrid=False, tickformat="%Y", ticks="outside", ticklen=3, dtick="M12")
    fig.update_yaxes(
        showgrid=True, gridcolor="rgba(128,128,128,0.15)", zeroline=False,
        ticksuffix="%", ticks="",
    )
    fig.update_layout(
        **{**LAYOUT_BASE, "margin": dict(l=0, r=45, t=8, b=0)},
        height=340, dragmode="select", selectdirection="h", clickmode="event+select",
    )
    return fig


# --------------------------------------------------------------------------
# Execução da Aplicação Principal
# --------------------------------------------------------------------------
try:
    df = carregar_dados()
    geo = carregar_geojson()
except Exception as exc:  # noqa: BLE001
    st.error(
        "Não foi possível carregar os dados. "
        "Execute `python fetch_data.py` no terminal e recarregue a página.\n\n"
        f"Detalhe do erro: {exc}"
    )
    st.stop()

versao = st.session_state.setdefault("versao", 0)
K_MAPA, K_BARRAS, K_SERIE = f"mapa_{versao}", f"barras_{versao}", f"serie_{versao}"

# ---- Barra Lateral: Controles e Filtros ------------------------------------
st.sidebar.title("Filtros de Controle")

regioes_sel = st.sidebar.multiselect(
    "Filtrar por Região",
    list(REGIOES.values()),
    default=list(REGIOES.values()),
    help="Filtra todas as visualizações do painel simultaneamente.",
)
if not regioes_sel:
    st.sidebar.warning("Selecione ao menos uma região para visualizar os dados.")
    st.stop()

periodos_ord = sorted(df["periodo"].unique(), reverse=True)
rotulos_dict = df.drop_duplicates("periodo").set_index("periodo")["rotulo"].to_dict()

ref_sidebar = st.sidebar.selectbox(
    "Trimestre de Referência",
    periodos_ord,
    format_func=lambda p: rotulos_dict[p],
    help="Define o período exibido no mapa e no ranking.",
)

if st.sidebar.button("Limpar Seleções Interativas", use_container_width=True):
    st.session_state["versao"] += 1
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Instruções de Interação:**\n"
    "- **Mapa / Ranking:** Clique para selecionar UFs.\n"
    "- **Série Temporal:** Arraste na horizontal para selecionar um intervalo.\n"
    "- **Sincronização:** Os gráficos e a tabela atualizam dinamicamente."
)

# ---- Filtragem do Dataset --------------------------------------------------
dv = df[df["regiao"].isin(regioes_sel)]
validos_uf = set(dv["uf_code"])

ufs_sel = (
    ufs_da_selecao(K_MAPA, validos_uf, fallback_key="location")
    | ufs_da_selecao(K_BARRAS, validos_uf)
)
periodos_sel = periodos_da_selecao(K_SERIE, set(df["periodo"]))

ref = max(periodos_sel) if periodos_sel else ref_sidebar
d_ref = dv[dv["periodo"] == ref]
ref_data = d_ref["data"].iloc[0] if len(d_ref) else dv["data"].max()

# ---- Cabeçalho Principal ---------------------------------------------------
st.title("Painel Analítico: Taxa de Desocupação por UF")
origem_txt = f"Trimestre de Referência: **{rotulos_dict[ref]}**"
if periodos_sel:
    origem_txt += " *(Definido via seleção na Série Temporal)*"

st.caption(
    f"{origem_txt} · População de 14 anos ou mais de idade · "
    "Fonte de dados: IBGE / PNAD Contínua Trimestral (SIDRA Tabela 4099)."
)

if ufs_sel:
    nomes_destaque = ", ".join(sorted(UF_SIGLA.get(u, u) for u in ufs_sel))
    st.info(f"📌 **UFs em destaque:** {nomes_destaque}")

# ---- Bloco 1: Visão Geral Espacial + Distribuição Categórica --------------
c1, c2 = st.columns([1.15, 0.85], gap="large")
with c1:
    st.subheader("1 · Visão Geral Espacial (Mapa)")
    st.plotly_chart(
        fig_mapa(d_ref, geo, ufs_sel),
        key=K_MAPA,
        on_select="rerun",
        selection_mode=("points", "box", "lasso"),
        use_container_width=True,
        config={"displaylogo": False},
    )

with c2:
    st.subheader("2 · Ranking de Desocupação (UFs)")
    st.plotly_chart(
        fig_barras(d_ref, ufs_sel),
        key=K_BARRAS,
        on_select="rerun",
        selection_mode=("points", "box"),
        use_container_width=True,
        config={"displaylogo": False},
    )

# ---- Bloco 2: Série Temporal + Painel de Detalhes ---------------------------
c3, c4 = st.columns([1.7, 1.0], gap="large")
with c3:
    st.subheader("3 · Evolução Temporal (Série Histórica)")
    st.plotly_chart(
        fig_serie(dv, ufs_sel, periodos_sel, ref_data),
        key=K_SERIE,
        on_select="rerun",
        selection_mode=("points", "box"),
        use_container_width=True,
        config={"displaylogo": False},
    )
    st.caption(
        "Linhas cinzas: total de UFs filtradas. "
        + ("Linhas coloridas: UFs selecionadas." if ufs_sel else "Linha azul: mediana agregada das UFs.")
    )

with c4:
    st.subheader("4 · Detalhes sob Demanda")
    alvo = d_ref[d_ref["uf_code"].isin(ufs_sel)] if ufs_sel else d_ref
    
    if alvo.empty:
        st.warning("Nenhum dado encontrado para os filtros ativos.")
    elif len(ufs_sel) == 1:
        linha = alvo.iloc[0]
        hist = dv[dv["uf_code"] == linha["uf_code"]]
        st.markdown(f"### **{linha['uf']}** ({linha['sigla']})")
        st.text(f"Região {linha['regiao']} · Período: {linha['rotulo']}")
        
        m1, m2 = st.columns(2)
        m1.metric("Taxa de Desocupação", f"{_num(linha['taxa'])}%")
        m2.metric("Posição no Ranking", f"{linha['posicao']}º de {linha['n_ufs']}")
        
        m3, m4 = st.columns(2)
        m3.metric("Vs. Trimestre Anterior", "—" if pd.isna(linha["var_tri"]) else f"{_num(linha['var_tri'], True)} p.p.")
        m4.metric("Vs. 12 Meses Antes", "—" if pd.isna(linha["var_ano"]) else f"{_num(linha['var_ano'], True)} p.p.")
        
        pico = hist.loc[hist["taxa"].idxmax()]
        vale = hist.loc[hist["taxa"].idxmin()]
        st.caption(
            f"📈 Máxima histórica: **{_num(pico['taxa'])}%** ({pico['rotulo']}) | "
            f"📉 Mínima histórica: **{_num(vale['taxa'])}%** ({vale['rotulo']})"
        )
    else:
        rotulo_grupo = f"{len(alvo)} UFs Selecionadas" if ufs_sel else f"{len(alvo)} UFs Exibidas"
        st.markdown(f"### **{rotulo_grupo}**")
        st.text(f"Período de Referência: {rotulos_dict[ref]}")
        
        a, b = st.columns(2)
        a.metric("Mediana do Grupo", f"{_num(alvo['taxa'].median())}%")
        b.metric("Amplitude", f"{_num(alvo['taxa'].max() - alvo['taxa'].min())} p.p.")
        
        mx, mn = alvo.loc[alvo["taxa"].idxmax()], alvo.loc[alvo["taxa"].idxmin()]
        a2, b2 = st.columns(2)
        a2.metric(f"Maior Taxa ({mx['sigla']})", f"{_num(mx['taxa'])}%")
        b2.metric(f"Menor Taxa ({mn['sigla']})", f"{_num(mn['taxa'])}%")

# ---- Bloco 3: Tabela Filtrada com Exportação (Details-on-Demand) ------------
st.markdown("---")
st.subheader("Tabela de Dados Filtrados")

periodos_tab = periodos_sel if periodos_sel else {ref}
tabela = dv[dv["periodo"].isin(periodos_tab)]
if ufs_sel:
    tabela = tabela[tabela["uf_code"].isin(ufs_sel)]

tabela = tabela.sort_values(["periodo", "taxa"], ascending=[False, False])
tabela_exibicao = tabela[
    ["uf", "regiao", "rotulo", "taxa", "var_tri", "var_ano", "posicao"]
].rename(
    columns={
        "uf": "Unidade da Federação",
        "regiao": "Região",
        "rotulo": "Trimestre",
        "taxa": "Taxa (%)",
        "var_tri": "Var. Trimestral (p.p.)",
        "var_ano": "Var. Anual (p.p.)",
        "posicao": "Posição no Ranking",
    }
)

st.dataframe(
    tabela_exibicao,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Taxa (%)": st.column_config.NumberColumn(format="%.1f"),
        "Var. Trimestral (p.p.)": st.column_config.NumberColumn(format="%+.1f"),
        "Var. Anual (p.p.)": st.column_config.NumberColumn(format="%+.1f"),
    },
)

st.download_button(
    label="📥 Baixar Tabela em CSV",
    data=tabela_exibicao.to_csv(index=False).encode("utf-8"),
    file_name=f"desocupacao_ibge_{ref}.csv",
    mime="text/csv",
)