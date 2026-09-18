# Mercado em Destaque — automação

Automação do relatório semanal "Mercado em Destaque" da equipe de Renda Fixa.

## Como funciona

1. Toda segunda-feira (09h BRT), o GitHub Actions roda `src/pipeline.py`:
   busca os dados (Treasury, ANBIMA, B3, JGP/IDEX), gera o texto do resumo
   via API da Claude e grava `data/latest.json` + um snapshot em
   `data/history/AAAA-MM-DD.json`, commitando tudo de volta no repositório.
2. O app Streamlit (`app.py`), publicado no Streamlit Community Cloud e
   conectado a este repositório, apenas lê `data/latest.json` e mostra o
   texto e os gráficos — sem nenhuma chamada de rede ao vivo.

Se uma fonte falhar numa semana, o pipeline registra um aviso em
`data/latest.json["avisos"]` e mantém a última versão bem-sucedida daquela
seção (`data/latest.json` só é sobrescrito quando há pelo menos dados de
Treasury; o histórico de ANBIMA/JGP é acumulado incrementalmente a cada
execução).

## Rodar localmente

```bash
pip install -r requirements.txt
python src/pipeline.py          # gera data/latest.json
streamlit run app.py            # abre o app localmente
```

Para gerar o texto do resumo, defina `ANTHROPIC_API_KEY` no ambiente.

## Configuração no GitHub

1. Crie o repositório e faça push deste projeto.
2. Em Settings → Secrets and variables → Actions, adicione o secret
   `ANTHROPIC_API_KEY`.
3. Em [share.streamlit.io](https://share.streamlit.io), conecte este
   repositório e aponte para `app.py`.
4. Rode o workflow manualmente uma vez (aba Actions → "Relatorio semanal" →
   Run workflow) antes de confiar no agendamento automático.

## Limitações conhecidas

- **Histórico de ANBIMA e JGP/IDEX**: essas fontes só oferecem publicamente
  uma janela curta de histórico (ANBIMA: ~5 dias úteis; JGP: ~1 mês). As
  comparações de "1 mês" e "6 meses" para essas séries, e o histórico
  plurianual dos gráficos de IDEX-DI/IDEX-Infra, dependem do próprio
  histórico acumulado em `data/history/` — ficam mais completos a cada
  semana que o pipeline roda, não desde o primeiro dia.
- **Gráfico "Spread de crédito por rating"** (curva AAA/AA/A por vértice,
  presente no relatório de referência) não foi replicado: o arquivo público
  da JGP não traz uma coluna de rating por debênture. Ficou fora do escopo
  até se identificar uma fonte para esse dado.
- **Debêntures individuais (ex.: CRVDA6) e captação de fundos (Bradesco)**:
  fora do escopo por decisão da equipe.
