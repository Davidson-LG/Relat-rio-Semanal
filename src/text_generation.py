"""Gera o paragrafo analitico semanal a partir dos deltas numericos calculados,
usando a API da Claude. O modelo e instruido a apenas descrever as variacoes
recebidas (nao inventar causas/noticias que nao estao nos dados).
"""

from __future__ import annotations

import json
import os

import anthropic

_SYSTEM_PROMPT = """\
Voce escreve o resumo semanal de mercado de renda fixa para o time de \
Renda Fixa de um fundo de pensao brasileiro (relatorio "Mercado em Destaque").

Estilo alvo (siga o tom e a estrutura, nao copie frases): paragrafos curtos, \
tecnicos, objetivos, em portugues do Brasil, citando os vertices e as \
variacoes em bps ou pontos percentuais. Cubra, nesta ordem, quando o dado \
estiver disponivel: (1) juros futuros/curva DI no Brasil, (2) juros reais \
(NTN-B) e inflacao implicita, (3) curva de juros americana, (4) spreads de \
credito privado (IDEX-DI e IDEX-Infra).

Regras importantes:
- Descreva SOMENTE o que os numeros fornecidos mostram (direcao e magnitude). \
Nao invente causas, noticias ou eventos macroeconomicos que nao estejam nos dados.
- Se um dado estiver ausente, simplesmente nao mencione esse tópico -- nao \
mencione a ausencia do dado.
- Nao use saudacoes, titulos ou assinatura. Devolva apenas o texto corrido do resumo.
"""


def gerar_texto_resumo(deltas: dict, reference_date: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY nao configurada")

    client = anthropic.Anthropic(api_key=api_key)
    payload = json.dumps({"data_referencia": reference_date, "deltas": deltas}, ensure_ascii=False, indent=2)

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=800,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Dados da semana:\n{payload}"}],
    )
    return "".join(block.text for block in message.content if block.type == "text").strip()
