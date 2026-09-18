"""Orquestra a geracao semanal do relatorio: busca dados, monta comparacoes,
gera o texto e grava data/latest.json + um snapshot em data/history/.

Uso: python src/pipeline.py
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import processing
import text_generation
from fetchers import jgp

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("pipeline")

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
HISTORY_DIR = DATA_DIR / "history"


def _safe(nome: str, fn):
    try:
        resultado = fn()
        logger.info("OK: %s", nome)
        return resultado
    except Exception as exc:
        logger.warning("FALHOU: %s (%s: %s)", nome, type(exc).__name__, exc)
        return None


def main() -> None:
    reference_date = processing.nearest_business_day(dt.date.today())
    logger.info("Gerando relatorio para %s", reference_date)

    warnings: list[str] = []

    treasury_cmp = _safe("US Treasury", lambda: processing.build_treasury_comparison(reference_date)) or {}
    curva_di_cmp = _safe("Curva DI (B3)", lambda: processing.build_curva_di_comparison(reference_date)) or {}
    ettj_pre_cmp = _safe("ETTJ Pre (ANBIMA)", lambda: processing.build_ettj_pre_comparison(reference_date)) or {}
    ettj_ipca_cmp = _safe("ETTJ IPCA (ANBIMA)", lambda: processing.build_ettj_ipca_comparison(reference_date)) or {}
    inflacao_cmp = _safe(
        "Inflacao implicita (ANBIMA)", lambda: processing.build_inflacao_implicita_comparison(reference_date)
    ) or {}

    idex_di_atual = _safe("IDEX-DI (JGP)", jgp.get_idex_di)
    idex_infra_atual = _safe("IDEX-Infra (JGP)", jgp.get_idex_infra)

    idex_di_series = processing.build_idex_series(idex_di_atual, "idex_di") if idex_di_atual is not None else None
    idex_infra_series = (
        processing.build_idex_series(idex_infra_atual, "idex_infra") if idex_infra_atual is not None else None
    )

    for nome, cmp_dict in [
        ("Treasury", treasury_cmp),
        ("Curva DI", curva_di_cmp),
        ("ETTJ Pre", ettj_pre_cmp),
        ("ETTJ IPCA", ettj_ipca_cmp),
        ("Inflacao implicita", inflacao_cmp),
    ]:
        if not cmp_dict:
            warnings.append(f"{nome}: fonte indisponivel nesta execucao, mantendo ultimo relatorio para essa secao")
        elif "1 semana" not in cmp_dict:
            warnings.append(f"{nome}: comparacao de 1 semana indisponivel nesta execucao")

    deltas = processing.build_deltas(
        treasury_cmp,
        curva_di_cmp,
        ettj_pre_cmp,
        ettj_ipca_cmp,
        inflacao_cmp,
        idex_di_series if idex_di_series is not None else __import__("pandas").DataFrame(),
        idex_infra_series if idex_infra_series is not None else __import__("pandas").DataFrame(),
    )

    texto = _safe("Geracao de texto (Claude)", lambda: text_generation.gerar_texto_resumo(deltas, str(reference_date)))
    if not texto:
        texto = "Texto indisponivel nesta execucao (falha na geracao automatica)."
        warnings.append("Texto do resumo semanal nao pode ser gerado nesta execucao")

    latest = {
        "gerado_em": dt.datetime.now().isoformat(timespec="seconds"),
        "data_referencia": str(reference_date),
        "texto": texto,
        "graficos": {
            "treasury": treasury_cmp,
            "curva_di": curva_di_cmp,
            "ettj_pre": ettj_pre_cmp,
            "ettj_ipca": ettj_ipca_cmp,
            "inflacao_implicita": inflacao_cmp,
            "idex_di": (idex_di_series.assign(Data=idex_di_series["Data"].astype(str)).to_dict(orient="records"))
            if idex_di_series is not None and not idex_di_series.empty
            else [],
            "idex_infra": (
                idex_infra_series.assign(Data=idex_infra_series["Data"].astype(str)).to_dict(orient="records")
            )
            if idex_infra_series is not None and not idex_infra_series.empty
            else [],
        },
        "avisos": warnings,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    latest_path = DATA_DIR / "latest.json"
    if latest["graficos"]["treasury"] or latest_path.exists():
        latest_path.write_text(json.dumps(latest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        logger.info("Gravado %s", latest_path)

    snapshot = {
        "idex_di": (
            idex_di_atual.assign(Data=idex_di_atual["Data"].astype(str)).to_dict(orient="records")
            if idex_di_atual is not None and not idex_di_atual.empty
            else []
        ),
        "idex_infra": (
            idex_infra_atual.assign(Data=idex_infra_atual["Data"].astype(str)).to_dict(orient="records")
            if idex_infra_atual is not None and not idex_infra_atual.empty
            else []
        ),
    }
    snapshot_path = HISTORY_DIR / f"{reference_date}.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info("Gravado %s", snapshot_path)

    if warnings:
        logger.warning("Avisos desta execucao:\n- %s", "\n- ".join(warnings))


if __name__ == "__main__":
    main()
