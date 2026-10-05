# Dashboard CinePET

O dashboard transforma as duas planilhas e a transcrição em tabelas derivadas sem modificar os arquivos originais.

## Tema da pesquisa

Analisar as concepções e compreensões dos discentes da Universidade Federal de Sergipe, Campus Professor Alberto Carvalho, sobre inclusão, relacionando-as com as perspectivas e as possibilidades para uma educação inclusiva.

## Atualizar os dados

Mantenha estes nomes de arquivo na pasta do projeto:

- `O Perigo de uma História Única (Responses).xlsx`
- `Wicked (Responses).xlsx`
- `Transcrição do grupo de Alana e Giselle CinePET.doc`
- `trascrição.txt`

Depois execute:

```bash
python scripts/atualizar_dados.py
```

O processamento atualiza `dados_tratados/` e `dashboard/data.js`.

## Abrir o painel

Abra `dashboard/index.html` no navegador. Se o navegador restringir arquivos locais, inicie um servidor somente neste computador:

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory dashboard
```

Depois acesse `http://127.0.0.1:8765/`.

## Saídas

- `respostas_unificadas.csv`: perfil padronizado e anonimizado.
- `respostas_qualitativas.csv`: respostas abertas e temas sugeridos.
- `transcricao_segmentada.csv`: falas separadas por participante.
- `dicionario_normalizacao.csv`: valores originais e tratados.
- `inconsistencias.csv`: situações que precisam de revisão humana.
- `manifesto_fontes.csv`: assinatura SHA-256 dos arquivos-base.
- `dados_dashboard.json`: pacote completo para análise externa.
- `relatorio_execucao.json`: resumo de cada atualização.

## Regras de segurança dos dados

- Os arquivos-base são apenas lidos.
- E-mails não são copiados para as tabelas tratadas nem para o dashboard.
- Cada resposta recebe um identificador anônimo estável.
- Valores ambíguos não são inventados; aparecem no relatório de inconsistências.
- A classificação temática é auxiliar e deve ser validada na análise acadêmica.
