"""Curva de juros americana (US Treasury Daily Par Yield Curve Rates).

Fonte publica, sem chave de API: home.treasury.gov.
"""

from __future__ import annotations

import datetime as dt
from xml.etree import ElementTree

import pandas as pd
import requests

_BASE_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
    "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
}

_TENORS = {
    "BC_1MONTH": "1 mes",
    "BC_3MONTH": "3 meses",
    "BC_6MONTH": "6 meses",
    "BC_1YEAR": "1 ano",
    "BC_2YEAR": "2 anos",
    "BC_5YEAR": "5 anos",
    "BC_7YEAR": "7 anos",
    "BC_10YEAR": "10 anos",
    "BC_20YEAR": "20 anos",
    "BC_30YEAR": "30 anos",
}


def _fetch_year(year: int) -> pd.DataFrame:
    resp = requests.get(_BASE_URL, params={
        "data": "daily_treasury_yield_curve",
        "field_tdr_date_value": year,
    }, timeout=30)
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.content)

    rows = []
    for entry in root.findall("atom:entry", _NS):
        props = entry.find("atom:content/m:properties", _NS)
        if props is None:
            continue
        date_el = props.find("d:NEW_DATE", _NS)
        if date_el is None or not date_el.text:
            continue
        row = {"data": date_el.text[:10]}
        for field, label in _TENORS.items():
            el = props.find(f"d:{field}", _NS)
            row[label] = float(el.text) if el is not None and el.text else None
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["data"] = pd.to_datetime(df["data"])
    return df.sort_values("data").reset_index(drop=True)


def get_yield_curve(reference_date: dt.date | None = None) -> pd.DataFrame:
    """Retorna a curva par yield diaria do Treasury para o ano da data de referencia.

    Cada linha e um dia; colunas sao os vertices (1 mes .. 30 anos).
    """
    reference_date = reference_date or dt.date.today()
    df = _fetch_year(reference_date.year)
    if df.empty and reference_date.month == 1:
        # inicio de ano: garante que o ano anterior tambem esteja disponivel para comparacoes
        df = _fetch_year(reference_date.year - 1)
    return df


def tenors_in_years() -> dict[str, float]:
    """Mapa vertice -> numero de anos, usado para plotar o eixo x."""
    return {
        "1 mes": 1 / 12,
        "3 meses": 3 / 12,
        "6 meses": 6 / 12,
        "1 ano": 1,
        "2 anos": 2,
        "5 anos": 5,
        "7 anos": 7,
        "10 anos": 10,
        "20 anos": 20,
        "30 anos": 30,
    }
