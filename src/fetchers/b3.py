"""Curva DI (mercado futuro de DI1 / ETTJ PRE da B3), via biblioteca `pyettj`
que baixa diretamente do site publico da B3 (sem login).
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pyettj.ettj as ettj


def get_curva_di(reference_date: dt.date) -> pd.DataFrame:
    """Curva DI x PRE da B3 para a data de referencia.

    Retorna vazio se a data cair em dia nao util ou sem pregao.
    """
    data_str = reference_date.strftime("%d/%m/%Y")
    try:
        df = ettj.get_ettj(data_str, curva="PRE")
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    df = df.rename(columns={"taxa": "taxa_di"})
    return df[["dias_corridos", "dias_uteis", "taxa_di"]].sort_values("dias_corridos").reset_index(
        drop=True
    )
