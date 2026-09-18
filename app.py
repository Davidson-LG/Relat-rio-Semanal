"""App Streamlit: exibe o ultimo relatorio "Mercado em Destaque" gerado pelo
pipeline (data/latest.json). Nao faz nenhuma chamada de rede ao vivo -- so le
o arquivo que o GitHub Actions gerou e commitou no repositorio.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA_PATH = Path(__file__).resolve().parent / "data" / "latest.json"

st.set_page_config(page_title="Mercado em Destaque", layout="wide")


@st.cache_data(ttl=3600)
def load_latest() -> dict | None:
    if not DATA_PATH.exists():
        return None
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def linha_treasury(fig: go.Figure, cmp: dict) -> None:
    for label, serie in cmp.items():
        pontos = sorted(serie["pontos"], key=lambda p: p["anos"])
        fig.add_trace(go.Scatter(
            x=[p["anos"] for p in pontos],
            y=[p["taxa"] for p in pontos],
            mode="lines+markers",
            name=f"{label} ({serie['data']})",
        ))
    fig.update_layout(xaxis_title="Anos", yaxis_title="Yield (%)")


def linha_curva_di(fig: go.Figure, cmp: dict) -> None:
    for label, serie in cmp.items():
        pontos = sorted(serie["pontos"], key=lambda p: p["dias_corridos"])
        fig.add_trace(go.Scatter(
            x=[p["dias_corridos"] for p in pontos],
            y=[p["taxa_di"] * 100 for p in pontos],
            mode="lines",
            name=f"{label} ({serie['data']})",
        ))
    fig.update_layout(xaxis_title="Dias corridos", yaxis_title="Taxa DI (% a.a.)")


def linha_ettj(fig: go.Figure, cmp: dict, campo_taxa: str, escala: float = 100) -> None:
    for label, serie in cmp.items():
        pontos = sorted(serie["pontos"], key=lambda p: p["dias_corridos"])
        fig.add_trace(go.Scatter(
            x=[p["dias_corridos"] for p in pontos],
            y=[p[campo_taxa] * escala for p in pontos],
            mode="lines+markers",
            name=f"{label} ({serie['data']})",
        ))
    fig.update_layout(xaxis_title="Dias corridos", yaxis_title="Taxa (% a.a.)")


def linha_serie_temporal(fig: go.Figure, registros: list[dict], campo: str, escala: float = 1, nome: str = "") -> None:
    df = pd.DataFrame(registros)
    if df.empty:
        return
    df["Data"] = pd.to_datetime(df["Data"])
    df = df.sort_values("Data")
    fig.add_trace(go.Scatter(x=df["Data"], y=df[campo] * escala, mode="lines", name=nome))


def grafico(titulo: str, plot_fn) -> None:
    st.subheader(titulo)
    fig = go.Figure()
    plot_fn(fig)
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    st.title("Mercado em Destaque")
    st.caption("Resumo semanal automatizado da Renda Fixa")

    latest = load_latest()
    if latest is None:
        st.warning(
            "Nenhum relatorio foi gerado ainda. Rode `python src/pipeline.py` "
            "(ou aguarde a primeira execucao agendada) para popular data/latest.json."
        )
        return

    st.markdown(f"**Referente a:** {latest['data_referencia']}  \n"
                f"**Gerado em:** {latest['gerado_em']}")

    if latest.get("avisos"):
        with st.expander("Avisos desta execucao", expanded=False):
            for aviso in latest["avisos"]:
                st.warning(aviso)

    st.markdown("### Resumo semanal")
    st.write(latest["texto"])

    graficos = latest["graficos"]

    col1, col2 = st.columns(2)
    with col1:
        if graficos.get("curva_di"):
            grafico("Curva DI (B3)", lambda fig: linha_curva_di(fig, graficos["curva_di"]))
    with col2:
        if graficos.get("treasury"):
            grafico("Curva de juros americana (Treasury)", lambda fig: linha_treasury(fig, graficos["treasury"]))

    col3, col4 = st.columns(2)
    with col3:
        if graficos.get("ettj_pre"):
            grafico("ETTJ Pre (titulos publicos)", lambda fig: linha_ettj(fig, graficos["ettj_pre"], "taxa_indicativa"))
    with col4:
        if graficos.get("ettj_ipca"):
            grafico(
                "ETTJ IPCA - Juro real (NTN-B)",
                lambda fig: linha_ettj(fig, graficos["ettj_ipca"], "taxa_indicativa"),
            )

    if graficos.get("inflacao_implicita"):
        grafico(
            "Inflacao implicita",
            lambda fig: linha_ettj(fig, graficos["inflacao_implicita"], "inflacao_implicita"),
        )

    col5, col6 = st.columns(2)
    with col5:
        if graficos.get("idex_di"):
            grafico(
                "IDEX-DI (spread medio ponderado, ex-estressados)",
                lambda fig: linha_serie_temporal(
                    fig, graficos["idex_di"], "spread_medio_ponderado", 100, "IDEX-DI"
                ),
            )
    with col6:
        if graficos.get("idex_infra"):
            grafico(
                "IDEX-Infra (numero indice)",
                lambda fig: linha_serie_temporal(fig, graficos["idex_infra"], "numero_indice", 1, "IDEX-Infra"),
            )

    st.caption(
        "Fontes: US Department of the Treasury, ANBIMA (via biblioteca pyield), "
        "B3 (via biblioteca pyettj), JGP/IDEX Analytics. Series historicas de ANBIMA e "
        "JGP sao acumuladas automaticamente a cada execucao semanal e crescem ao longo do tempo."
    )


if __name__ == "__main__":
    main()
