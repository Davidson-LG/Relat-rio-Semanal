"""IDEX-DI e IDEX-Infra (JGP / IDEX Analytics).

As bases de dados sao arquivos Excel publicos, sem login, hospedados em um
bucket S3 da JGP. Cada linha e um ativo (debenture) em uma data; o indice
(spread medio ponderado para o IDEX-DI, numero indice para o IDEX-Infra) e
calculado agregando essas linhas por data, replicando o calculo que a equipe
de Renda Fixa da Forluz ja faz manualmente.
"""

from __future__ import annotations

import io

import pandas as pd
import requests

IDEX_DI_URL = "https://jgp-credito-public-s3.s3.us-east-1.amazonaws.com/idex/idex_cdi_geral_datafile.xlsx"
IDEX_INFRA_URL = "https://jgp-credito-public-s3.s3.us-east-1.amazonaws.com/idex/idex_infra_geral_datafile.xlsx"

# Ativos estressados removidos do calculo, conforme pratica da equipe de Renda Fixa.
EMISSORES_EXCLUIDOS = [
    "Americanas",
    "Aeris",
    "Elfa Medicamentos",
    "Light",
    "Viveo",
    "Raizen",
    "Raízen",
    "Kora Saude",
    "Kora Saúde",
    "CBD",
    "Ligga Telecomunicacoes",
    "Ligga Telecomunicações",
]


def _download_detalhado(url: str) -> pd.DataFrame:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    df = pd.read_excel(io.BytesIO(resp.content), sheet_name="Detalhado")
    df["Data"] = pd.to_datetime(df["Data"])
    return df


def _excluir_estressados(df: pd.DataFrame) -> pd.DataFrame:
    emissor_col = next(c for c in df.columns if c.startswith("Emissor"))
    padrao = "|".join(EMISSORES_EXCLUIDOS)
    mask = ~df[emissor_col].str.contains(padrao, case=False, na=False)
    return df[mask]


def get_idex_di() -> pd.DataFrame:
    """Serie historica do IDEX-DI: spread de compra medio ponderado por data."""
    df = _download_detalhado(IDEX_DI_URL)
    df = _excluir_estressados(df)
    peso_col = next(c for c in df.columns if c.startswith("Peso no"))
    spread_col = next(c for c in df.columns if c.startswith("Spread de compra"))

    df = df.dropna(subset=[peso_col, spread_col])
    df["_ponderado"] = df[peso_col] * df[spread_col]

    serie = (
        df.groupby("Data")
        .agg(peso_total=(peso_col, "sum"), ponderado_total=("_ponderado", "sum"))
        .assign(spread_medio_ponderado=lambda d: d["ponderado_total"] / d["peso_total"])
        .reset_index()[["Data", "spread_medio_ponderado"]]
        .sort_values("Data")
        .reset_index(drop=True)
    )
    return serie


def get_idex_infra() -> pd.DataFrame:
    """Serie historica do IDEX-Infra: numero indice (nivel) por data."""
    df = _download_detalhado(IDEX_INFRA_URL)
    indice_col = next(c for c in df.columns if "ndice" in c and "mero" in c.lower())

    serie = (
        df.groupby("Data")[indice_col]
        .mean()
        .reset_index()
        .rename(columns={indice_col: "numero_indice"})
        .sort_values("Data")
        .reset_index(drop=True)
    )
    return serie
