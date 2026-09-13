"""Interactive dashboard for monitoring Brazilian economic indicators."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
SNAPSHOT_PATH = APP_DIR / "data" / "economic_monthly.csv"
LOGGER = logging.getLogger(__name__)


def app_setting(name: str, default: str) -> str:
    """Read deployment settings from the environment or Streamlit secrets."""
    environment_value = os.getenv(name)
    if environment_value:
        return environment_value
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


DATA_MODE = app_setting("APP_DATA_MODE", "snapshot").lower()

COLORS = {
    "green": "#22C55E",
    "mint": "#5EEAD4",
    "amber": "#FBBF24",
    "blue": "#60A5FA",
    "rose": "#FB7185",
    "text": "#EAF4EF",
    "muted": "#91A39A",
    "grid": "rgba(145, 163, 154, 0.16)",
    "paper": "rgba(0,0,0,0)",
}

st.set_page_config(
    page_title="Pulso Econômico Brasil",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(circle at 85% 5%, rgba(34,197,94,.11), transparent 27rem),
          linear-gradient(180deg, #08110e 0%, #0a1511 100%);
      }
      [data-testid="stSidebar"] { border-right: 1px solid rgba(145,163,154,.15); }
      [data-testid="stMetric"] {
        background: linear-gradient(145deg, rgba(23,42,34,.94), rgba(13,27,22,.94));
        border: 1px solid rgba(145,163,154,.18);
        padding: 1rem 1.05rem;
        border-radius: 16px;
      }
      [data-testid="stMetricValue"] { color: #f4fbf7; }
      [data-testid="stMetricDelta"] svg { display: none; }
      .eyebrow { color:#5eead4; font-size:.78rem; letter-spacing:.12em; text-transform:uppercase; }
      .hero-title { font-size:clamp(2rem,5vw,4.6rem); line-height:.98; font-weight:700; margin:.35rem 0 .75rem; }
      .hero-copy { color:#a9bbb1; max-width:760px; font-size:1.02rem; }
      .status-line { color:#91a39a; font-size:.84rem; }
      .update-status {
        background:linear-gradient(145deg, rgba(34,197,94,.16), rgba(16,185,129,.08));
        border:1px solid rgba(34,197,94,.34); border-radius:12px;
        padding:.8rem .9rem; margin:.25rem 0 .7rem;
      }
      .update-status-title { color:#bbf7d0; font-size:.9rem; font-weight:700; }
      .update-status-dot {
        display:inline-block; width:.5rem; height:.5rem; margin-right:.5rem;
        border-radius:999px; background:#22c55e; box-shadow:0 0 10px rgba(34,197,94,.72);
      }
      .update-status-detail { color:#91a39a; font-size:.76rem; margin-top:.35rem; }
      .snapshot-status { border-color:rgba(145,163,154,.22); background:rgba(23,42,34,.58); }
      .snapshot-status .update-status-title { color:#cfe1d7; }
      .snapshot-status .update-status-dot { background:#91a39a; box-shadow:none; }
      .insight {
        background:rgba(23,42,34,.72); border:1px solid rgba(94,234,212,.18);
        border-radius:14px; padding:1rem 1.1rem; color:#cfe1d7;
      }
      div[data-testid="stPlotlyChart"] { border:1px solid rgba(145,163,154,.13); border-radius:16px; overflow:hidden; }
      .stTabs [data-baseweb="tab-list"] { gap:.4rem; }
      .stTabs [data-baseweb="tab"] { border-radius:999px; padding:.45rem .9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600)
def load_snapshot() -> pd.DataFrame:
    frame = pd.read_csv(SNAPSHOT_PATH, parse_dates=["month", "last_observation_date", "loaded_at"])
    for column in ["value", "monthly_average"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


@st.cache_data(ttl=3600)
def load_live() -> pd.DataFrame:
    connection = st.connection("snowflake")
    database = app_setting("SNOWFLAKE_DATABASE", "DBT_DB")
    schema = app_setting("SNOWFLAKE_ANALYTICS_SCHEMA", "DBT_SCHEMA")
    if not database.replace("_", "").isalnum() or not schema.replace("_", "").isalnum():
        raise ValueError("Invalid Snowflake database or schema identifier")
    query = f"""
        select
            month,
            series_code,
            indicator_key,
            indicator_name,
            category,
            unit,
            frequency,
            end_of_period_value as value,
            monthly_average,
            observation_count,
            last_observation_date,
            loaded_at
        from {database}.{schema}.mart_economic_monthly
        order by month, series_code
    """
    frame = connection.query(query, ttl=3600)
    frame.columns = [column.lower() for column in frame.columns]
    for column in ["month", "last_observation_date", "loaded_at"]:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
    for column in ["value", "monthly_average"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def load_data() -> tuple[pd.DataFrame, str]:
    if DATA_MODE == "live":
        try:
            return load_live(), "Atualização automática"
        except Exception:  # Keep the public view available during temporary warehouse outages.
            LOGGER.exception("Live data source unavailable; falling back to the local snapshot")
            st.warning("A atualização automática está temporariamente indisponível. Exibindo a última base consolidada.")
    return load_snapshot(), "Base consolidada"


def apply_chart_style(figure: go.Figure, *, height: int = 390) -> go.Figure:
    figure.update_layout(
        height=height,
        margin=dict(l=16, r=20, t=58, b=16),
        paper_bgcolor=COLORS["paper"],
        plot_bgcolor=COLORS["paper"],
        font=dict(color=COLORS["text"], family="Inter, Segoe UI, sans-serif"),
        hoverlabel=dict(bgcolor="#14251e", font_color=COLORS["text"], bordercolor="#29483b"),
        legend=dict(
            title_text="",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.34,
        ),
        xaxis=dict(gridcolor=COLORS["grid"], zeroline=False),
        yaxis=dict(gridcolor=COLORS["grid"], zeroline=False),
    )
    return figure


def format_br(value: float, decimals: int = 2) -> str:
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def latest_value(frame: pd.DataFrame, key: str, column: str = "value") -> tuple[float, pd.Timestamp]:
    subset = frame.loc[frame["indicator_key"] == key].sort_values("month")
    if subset.empty:
        return float("nan"), pd.NaT
    row = subset.iloc[-1]
    return float(row[column]), row["month"]


def previous_delta(frame: pd.DataFrame, key: str, column: str = "value") -> float | None:
    values = frame.loc[frame["indicator_key"] == key].sort_values("month")[column].dropna()
    if len(values) < 2:
        return None
    return float(values.iloc[-1] - values.iloc[-2])


def ipca_twelve_months(frame: pd.DataFrame) -> pd.DataFrame:
    ipca = frame.loc[frame["indicator_key"] == "ipca_monthly", ["month", "value"]].sort_values("month").copy()
    ipca["ipca_12m"] = (
        (1 + ipca["value"] / 100)
        .rolling(12)
        .apply(lambda values: values.prod(), raw=True)
        .sub(1)
        .mul(100)
    )
    return ipca


data, source_label = load_data()
if data.empty:
    st.error("Nenhuma observação disponível.")
    st.stop()

minimum_month = data["month"].min().date()
maximum_month = data["month"].max().date()
latest_loaded_at = pd.to_datetime(data["loaded_at"], errors="coerce", utc=True).max()
latest_sync_label = (
    latest_loaded_at.tz_convert("America/Sao_Paulo").strftime("%d/%m/%Y às %H:%M")
    if pd.notna(latest_loaded_at)
    else "não informada"
)

with st.sidebar:
    st.markdown("### Pulso Econômico")
    st.caption("Indicadores econômicos consolidados")
    start_month, end_month = st.date_input(
        "Período",
        value=(max(minimum_month, maximum_month.replace(year=max(2020, maximum_month.year - 3))), maximum_month),
        min_value=minimum_month,
        max_value=maximum_month,
    )
    selected_categories = st.multiselect(
        "Categorias",
        sorted(data["category"].dropna().unique()),
        default=sorted(data["category"].dropna().unique()),
    )
    st.divider()
    if source_label == "Atualização automática":
        st.markdown(
            f"""
            <div class="update-status">
              <div class="update-status-title"><span class="update-status-dot"></span>Atualização automática</div>
              <div class="update-status-detail">Última sincronização: {latest_sync_label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Agendada diariamente às 06:00 · cache de até 1 hora")
    else:
        st.markdown(
            """
            <div class="update-status snapshot-status">
              <div class="update-status-title"><span class="update-status-dot"></span>Base consolidada</div>
              <div class="update-status-detail">Última versão disponível para consulta</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.caption("Dados: Sistema Gerenciador de Séries Temporais — Banco Central do Brasil")

filtered = data.loc[
    data["month"].dt.date.between(start_month, end_month)
    & data["category"].isin(selected_categories)
].copy()

st.markdown('<div class="eyebrow">Panorama macroeconômico · Brasil</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">Pulso Econômico<br>Brasil</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-copy">Acompanhamento integrado de juros, inflação, câmbio e mercado de trabalho.</div>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<div class="status-line">● Atualizado até {maximum_month:%d/%m/%Y} · {len(data):,} registros mensais consolidados</div>',
    unsafe_allow_html=True,
)

overview_tab, indicators_tab, quality_tab, about_tab = st.tabs(
    ["Visão geral", "Séries históricas", "Qualidade dos dados", "Metodologia e fontes"]
)

with overview_tab:
    st.write("")
    selic, _ = latest_value(filtered, "selic_target")
    usd, _ = latest_value(filtered, "usd_brl")
    unemployment, _ = latest_value(filtered, "unemployment")
    ipca_12m_frame = ipca_twelve_months(filtered)
    ipca_12m = float(ipca_12m_frame["ipca_12m"].dropna().iloc[-1]) if ipca_12m_frame["ipca_12m"].notna().any() else float("nan")

    columns = st.columns(4)
    columns[0].metric("Meta Selic", f"{format_br(selic)}% a.a.", delta=f"{format_br(previous_delta(filtered, 'selic_target') or 0)} p.p.")
    columns[1].metric("IPCA acumulado", f"{format_br(ipca_12m)}%", delta="12 meses", delta_color="off")
    columns[2].metric("Dólar comercial", f"R$ {format_br(usd)}", delta=f"{format_br(previous_delta(filtered, 'usd_brl') or 0)} no mês")
    columns[3].metric("Desocupação", f"{format_br(unemployment, 1)}%", delta=f"{format_br(previous_delta(filtered, 'unemployment') or 0, 1)} p.p.", delta_color="inverse")

    left, right = st.columns([1.65, 1])
    with left:
        selic_history = filtered.loc[filtered["indicator_key"] == "selic_target", ["month", "value"]].rename(columns={"value": "Meta Selic"})
        macro = selic_history.merge(ipca_12m_frame[["month", "ipca_12m"]], on="month", how="outer").sort_values("month")
        macro_long = macro.melt("month", var_name="Indicador", value_name="Percentual")
        macro_long["Indicador"] = macro_long["Indicador"].replace({"ipca_12m": "IPCA 12 meses"})
        figure = px.line(
            macro_long,
            x="month",
            y="Percentual",
            color="Indicador",
            color_discrete_map={"Meta Selic": COLORS["green"], "IPCA 12 meses": COLORS["mint"]},
            title="Juros e inflação",
        )
        figure.update_traces(line_width=3, hovertemplate="%{x|%b/%Y}<br>%{y:.2f}%<extra>%{fullData.name}</extra>")
        figure.update_yaxes(title="%", ticksuffix="%")
        figure.update_xaxes(title=None)
        st.plotly_chart(apply_chart_style(figure), width="stretch")

    with right:
        usd_history = filtered.loc[filtered["indicator_key"] == "usd_brl"].sort_values("month")
        figure = px.area(
            usd_history,
            x="month",
            y="monthly_average",
            title="Dólar médio mensal",
            color_discrete_sequence=[COLORS["amber"]],
        )
        figure.update_traces(line_width=2.5, fillcolor="rgba(251,191,36,.12)", hovertemplate="%{x|%b/%Y}<br>R$ %{y:.3f}<extra></extra>")
        figure.update_yaxes(title="R$/US$", tickprefix="R$ ")
        figure.update_xaxes(title=None)
        st.plotly_chart(apply_chart_style(figure), width="stretch")

    if not pd.isna(ipca_12m) and not pd.isna(selic):
        spread = selic - ipca_12m
        st.markdown(
            f'<div class="insight"><strong>Leitura rápida:</strong> a diferença entre a Meta Selic e o IPCA acumulado está em <strong>{format_br(spread)} p.p.</strong> no período mais recente.</div>',
            unsafe_allow_html=True,
        )

with indicators_tab:
    indicator_options = filtered[["indicator_key", "indicator_name"]].drop_duplicates().set_index("indicator_name")["indicator_key"]
    selected_name = st.selectbox("Indicador", indicator_options.index.tolist())
    selected_key = indicator_options[selected_name]
    indicator = filtered.loc[filtered["indicator_key"] == selected_key].sort_values("month")
    figure = px.line(indicator, x="month", y="value", markers=True, title=selected_name, color_discrete_sequence=[COLORS["green"]])
    figure.update_traces(line_width=3, marker_size=6, hovertemplate="%{x|%b/%Y}<br>%{y:.3f}<extra></extra>")
    figure.update_xaxes(title=None)
    figure.update_yaxes(title=indicator["unit"].iloc[-1] if not indicator.empty else None)
    st.plotly_chart(apply_chart_style(figure, height=460), width="stretch")
    st.download_button(
        "Baixar recorte em CSV",
        indicator.to_csv(index=False).encode("utf-8"),
        file_name=f"{selected_key}.csv",
        mime="text/csv",
    )

with quality_tab:
    expected_months = pd.period_range(data["month"].min(), data["month"].max(), freq="M")
    quality_rows = []
    for key, group in data.groupby("indicator_key"):
        observed = set(group["month"].dt.to_period("M"))
        missing = len(set(expected_months) - observed)
        quality_rows.append(
            {
                "Indicador": group["indicator_name"].iloc[0],
                "Primeiro período": group["month"].min().date(),
                "Último período": group["month"].max().date(),
                "Meses disponíveis": group["month"].nunique(),
                "Lacunas no intervalo global": missing,
                "Observações de origem": int(group["observation_count"].sum()),
            }
        )
    quality = pd.DataFrame(quality_rows).sort_values("Indicador")
    q1, q2, q3 = st.columns(3)
    q1.metric("Indicadores", data["indicator_key"].nunique())
    q2.metric("Chaves duplicadas", int(data.duplicated(["month", "series_code"]).sum()))
    q3.metric("Valores nulos", int(data["value"].isna().sum()))
    st.dataframe(quality, width="stretch", hide_index=True)
    st.caption("As lacunas são calculadas sobre o intervalo global; séries com início posterior podem apresentar lacunas esperadas.")

with about_tab:
    st.markdown(
        """
        ### Metodologia

        Os indicadores são obtidos no Sistema Gerenciador de Séries Temporais do Banco
        Central do Brasil e consolidados em frequência mensal para permitir comparações
        consistentes ao longo do tempo.

        - **Meta Selic:** valor vigente no encerramento de cada mês.
        - **IPCA:** variação mensal; o acumulado em 12 meses é calculado de forma composta.
        - **Dólar comercial:** média das observações diárias no mês.
        - **Taxa de desocupação:** último valor mensal publicado.

        A base passa por controles de unicidade, completude, relacionamentos e faixas
        válidas antes de ser disponibilizada para consulta.

        **Unidade de análise:** um indicador por mês.  
        **Fonte primária:** Banco Central do Brasil — SGS.
        """
    )
