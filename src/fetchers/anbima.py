"""ETTJ (pre e IPCA/juro real) e inflacao implicita, a partir das taxas
indicativas de titulos publicos publicadas pela propria ANBIMA (via biblioteca
`pyield`, sem scraping de HTML nem credenciais).
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pyield


def _taxas(reference_date: dt.date) -> pd.DataFrame:
    df = pyield.anbima.taxas.buscar(reference_date)
    if df.is_empty():
        return pd.DataFrame()
    pdf = df.to_pandas()
    pdf["data_vencimento"] = pd.to_datetime(pdf["data_vencimento"])
    pdf["dias_corridos"] = (pdf["data_vencimento"] - pd.Timestamp(reference_date)).dt.days
    return pdf


def get_ettj_pre(reference_date: dt.date) -> pd.DataFrame:
    """Curva pre (LTN + NTN-F), taxa indicativa (% a.a.) por vertice em dias corridos."""
    pdf = _taxas(reference_date)
    if pdf.empty:
        return pdf
    curva = pdf[pdf["titulo"].isin(["LTN", "NTN-F"])]
    return curva[["dias_corridos", "data_vencimento", "titulo", "taxa_indicativa"]].sort_values(
        "dias_corridos"
    ).reset_index(drop=True)


def get_ettj_ipca(reference_date: dt.date) -> pd.DataFrame:
    """Curva de juro real (NTN-B), taxa indicativa (% a.a.) por vertice em dias corridos."""
    pdf = _taxas(reference_date)
    if pdf.empty:
        return pdf
    curva = pdf[pdf["titulo"] == "NTN-B"]
    return curva[["dias_corridos", "data_vencimento", "taxa_indicativa"]].sort_values(
        "dias_corridos"
    ).reset_index(drop=True)


def get_inflacao_implicita(reference_date: dt.date) -> pd.DataFrame:
    """Inflacao implicita (breakeven), calculada entre NTN-B (real) e LTN/NTN-F (nominal)."""
    pdf = _taxas(reference_date)
    if pdf.empty:
        return pd.DataFrame()

    real = pdf[pdf["titulo"] == "NTN-B"].sort_values("data_vencimento")
    nominal = pdf[pdf["titulo"].isin(["LTN", "NTN-F"])].sort_values("data_vencimento")
    if real.empty or nominal.empty:
        return pd.DataFrame()

    resultado = pyield.ntnb.implicitas(
        data_liquidacao=reference_date,
        vencimentos_tir=real["data_vencimento"].tolist(),
        taxas_tir=real["taxa_indicativa"].tolist(),
        vencimentos_nominais=nominal["data_vencimento"].tolist(),
        taxas_nominais=nominal["taxa_indicativa"].tolist(),
    ).to_pandas()

    resultado = resultado.dropna(subset=["inflacao_implicita"])
    resultado["data_vencimento"] = pd.to_datetime(resultado["data_vencimento"])
    resultado["dias_corridos"] = (resultado["data_vencimento"] - pd.Timestamp(reference_date)).dt.days
    return resultado[["dias_corridos", "data_vencimento", "inflacao_implicita"]].sort_values(
        "dias_corridos"
    ).reset_index(drop=True)
