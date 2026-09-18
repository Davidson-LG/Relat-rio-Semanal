"""Monta as series comparativas (atual vs 1 semana / 1 mes / 6 meses) usadas
nos graficos, e os deltas numericos usados na geracao do texto.

Fontes com profundidade historica nativa (Treasury, B3/pyettj) sao
consultadas diretamente para cada data de comparacao. Fontes sem
profundidade historica publica suficiente (ANBIMA, JGP) dependem do
historico proprio acumulado em data/history/.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Callable

import pandas as pd

from fetchers import anbima, b3, jgp, treasury

HISTORY_DIR = Path(__file__).resolve().parent.parent / "data" / "history"
logger = logging.getLogger("pipeline.processing")


def nearest_business_day(reference: dt.date) -> dt.date:
    d = reference
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def _nearest_available(
    fetch_fn: Callable[[dt.date], pd.DataFrame], target: dt.date, max_lookback: int = 5
) -> tuple[pd.DataFrame, dt.date | None]:
    """Tenta buscar dados na data alvo, recuando ate `max_lookback` dias uteis
    se o pregao nao existir (feriado, fim de semana etc.)."""
    d = target
    tried = 0
    last_error: Exception | None = None
    while tried <= max_lookback:
        d_util = nearest_business_day(d)
        try:
            df = fetch_fn(d_util)
            last_error = None
        except Exception as exc:
            df = pd.DataFrame()
            last_error = exc
        if not df.empty:
            return df, d_util
        d -= dt.timedelta(days=1)
        tried += 1
    if last_error is not None:
        logger.warning(
            "%s: todas as %d tentativas falharam, ultimo erro: %s: %s",
            getattr(fetch_fn, "__module__", fetch_fn), max_lookback + 1, type(last_error).__name__, last_error,
        )
    else:
        logger.warning(
            "%s: todas as %d tentativas retornaram vazio (sem excecao)",
            getattr(fetch_fn, "__module__", fetch_fn), max_lookback + 1,
        )
    return pd.DataFrame(), None


# ---------------------------------------------------------------------------
# Treasury (profundidade historica nativa)
# ---------------------------------------------------------------------------

def build_treasury_comparison(reference_date: dt.date) -> dict:
    offsets = {"atual": 0, "1 semana": 7, "1 mes": 30, "6 meses": 182}
    result = {}
    for label, days in offsets.items():
        target = reference_date - dt.timedelta(days=days)
        year_df = treasury.get_yield_curve(target)
        if year_df.empty:
            continue
        year_df = year_df[year_df["data"] <= pd.Timestamp(target)]
        if year_df.empty:
            continue
        row = year_df.iloc[-1]
        vertices = treasury.tenors_in_years()
        result[label] = {
            "data": row["data"].strftime("%Y-%m-%d"),
            "pontos": [{"vertice": v, "anos": anos, "taxa": row[v]} for v, anos in vertices.items()],
        }
    return result


# ---------------------------------------------------------------------------
# B3 - curva DI (profundidade historica nativa via pyettj)
# ---------------------------------------------------------------------------

def build_curva_di_comparison(reference_date: dt.date) -> dict:
    offsets = {"atual": 0, "1 semana": 7, "1 ano": 365}
    result = {}
    for label, days in offsets.items():
        target = reference_date - dt.timedelta(days=days)
        df, used_date = _nearest_available(b3.get_curva_di, target)
        if df.empty:
            continue
        result[label] = {
            "data": used_date.strftime("%Y-%m-%d"),
            "pontos": df.to_dict(orient="records"),
        }
    return result


# ---------------------------------------------------------------------------
# ANBIMA - ETTJ pre / IPCA / inflacao implicita
# (retencao publica curta -> combina consulta direta + historico proprio)
# ---------------------------------------------------------------------------

def _anbima_current_and_recent(reference_date: dt.date, fetch_fn) -> dict:
    result = {}
    df_atual, d_atual = _nearest_available(fetch_fn, reference_date)
    if not df_atual.empty:
        result["atual"] = {"data": d_atual.strftime("%Y-%m-%d"), "pontos": df_atual.to_dict(orient="records")}

    df_1sem, d_1sem = _nearest_available(fetch_fn, reference_date - dt.timedelta(days=7), max_lookback=3)
    if not df_1sem.empty:
        result["1 semana"] = {"data": d_1sem.strftime("%Y-%m-%d"), "pontos": df_1sem.to_dict(orient="records")}

    return result


def build_ettj_pre_comparison(reference_date: dt.date) -> dict:
    return _anbima_current_and_recent(reference_date, anbima.get_ettj_pre)


def build_ettj_ipca_comparison(reference_date: dt.date) -> dict:
    return _anbima_current_and_recent(reference_date, anbima.get_ettj_ipca)


def build_inflacao_implicita_comparison(reference_date: dt.date) -> dict:
    return _anbima_current_and_recent(reference_date, anbima.get_inflacao_implicita)


# ---------------------------------------------------------------------------
# JGP - IDEX-DI / IDEX-Infra
# (arquivo publico so tem ~1 mes -> mescla com historico proprio acumulado)
# ---------------------------------------------------------------------------

def _load_history_series(key: str) -> pd.DataFrame:
    """Le todos os snapshots salvos em data/history e reconstroi a serie de `key`."""
    rows = []
    if HISTORY_DIR.exists():
        for f in sorted(HISTORY_DIR.glob("*.json")):
            try:
                snap = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            for point in snap.get(key, []):
                rows.append(point)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["Data"] = pd.to_datetime(df["Data"])
    return df.drop_duplicates(subset=["Data"]).sort_values("Data")


def build_idex_series(current: pd.DataFrame, key: str) -> pd.DataFrame:
    historico = _load_history_series(key)
    current = current.copy()
    current["Data"] = pd.to_datetime(current["Data"])
    combinado = pd.concat([historico, current], ignore_index=True)
    return combinado.drop_duplicates(subset=["Data"]).sort_values("Data").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Deltas para o texto narrativo
# ---------------------------------------------------------------------------

def _ponto_mais_proximo(pontos: list[dict], alvo_dias: int, chave_dias: str = "dias_corridos"):
    if not pontos:
        return None
    return min(pontos, key=lambda p: abs(p.get(chave_dias, 0) - alvo_dias))


def build_deltas(
    treasury_cmp: dict,
    curva_di_cmp: dict,
    ettj_pre_cmp: dict,
    ettj_ipca_cmp: dict,
    inflacao_cmp: dict,
    idex_di_series: pd.DataFrame,
    idex_infra_series: pd.DataFrame,
) -> dict:
    deltas = {}

    if "atual" in treasury_cmp and "1 semana" in treasury_cmp:
        for p_atual, p_1sem in zip(treasury_cmp["atual"]["pontos"], treasury_cmp["1 semana"]["pontos"]):
            if p_atual["vertice"] == "10 anos":
                deltas["treasury_10y"] = {
                    "atual": p_atual["taxa"],
                    "1_semana_atras": p_1sem["taxa"],
                    "delta_bps": round((p_atual["taxa"] - p_1sem["taxa"]) * 100, 1),
                }

    if "atual" in curva_di_cmp and "1 semana" in curva_di_cmp:
        alvo = _ponto_mais_proximo(curva_di_cmp["atual"]["pontos"], 365)
        anterior = _ponto_mais_proximo(curva_di_cmp["1 semana"]["pontos"], 365)
        if alvo and anterior:
            deltas["curva_di_1ano"] = {
                "atual": alvo["taxa_di"],
                "1_semana_atras": anterior["taxa_di"],
                "delta_bps": round((alvo["taxa_di"] - anterior["taxa_di"]) * 100, 1),
            }

    if "atual" in ettj_pre_cmp and "1 semana" in ettj_pre_cmp:
        alvo = _ponto_mais_proximo(ettj_pre_cmp["atual"]["pontos"], 1260)
        anterior = _ponto_mais_proximo(ettj_pre_cmp["1 semana"]["pontos"], 1260)
        if alvo and anterior:
            deltas["ettj_pre_5anos"] = {
                "atual": alvo["taxa_indicativa"],
                "1_semana_atras": anterior["taxa_indicativa"],
                "delta_bps": round((alvo["taxa_indicativa"] - anterior["taxa_indicativa"]) * 100, 1),
            }

    if "atual" in ettj_ipca_cmp and "1 semana" in ettj_ipca_cmp:
        alvo = _ponto_mais_proximo(ettj_ipca_cmp["atual"]["pontos"], 1260)
        anterior = _ponto_mais_proximo(ettj_ipca_cmp["1 semana"]["pontos"], 1260)
        if alvo and anterior:
            deltas["ettj_ipca_5anos"] = {
                "atual": alvo["taxa_indicativa"],
                "1_semana_atras": anterior["taxa_indicativa"],
                "delta_bps": round((alvo["taxa_indicativa"] - anterior["taxa_indicativa"]) * 100, 1),
            }

    if "atual" in inflacao_cmp and "1 semana" in inflacao_cmp:
        alvo = _ponto_mais_proximo(inflacao_cmp["atual"]["pontos"], 1260)
        anterior = _ponto_mais_proximo(inflacao_cmp["1 semana"]["pontos"], 1260)
        if alvo and anterior:
            deltas["inflacao_implicita_5anos"] = {
                "atual": alvo["inflacao_implicita"],
                "1_semana_atras": anterior["inflacao_implicita"],
                "delta_bps": round((alvo["inflacao_implicita"] - anterior["inflacao_implicita"]) * 100, 1),
            }

    if len(idex_di_series) >= 2:
        atual, anterior = idex_di_series.iloc[-1], idex_di_series.iloc[-2]
        deltas["idex_di"] = {
            "atual": atual["spread_medio_ponderado"],
            "anterior": anterior["spread_medio_ponderado"],
            "delta_bps": round((atual["spread_medio_ponderado"] - anterior["spread_medio_ponderado"]) * 100, 1),
        }

    if len(idex_infra_series) >= 2:
        atual, anterior = idex_infra_series.iloc[-1], idex_infra_series.iloc[-2]
        deltas["idex_infra"] = {
            "atual": atual["numero_indice"],
            "anterior": anterior["numero_indice"],
        }

    return deltas
