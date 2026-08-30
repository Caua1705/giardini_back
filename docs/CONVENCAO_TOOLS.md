# CONVENCAO_TOOLS.md — Convenção única das ferramentas HTTP da Júlia

Vale para os **quatro domínios**: `finance` (agora), `reservations` (em seguida),
`inventory` e `marketing` (futuro).

A Júlia é **um agente só**. Não há orquestrador, fila, roteador nem serviço novo: há
este backend FastAPI e um conjunto de rotas HTTP que o agente chama como ferramentas.
A camada de ferramentas **cresce por adição de rota** — nunca por reescrita das que já
existem e nunca por um serviço à parte.

O documento fixa seis coisas: prefixo de path, nomes de parâmetro, envelope de
resposta, limite de tamanho, sinalização de truncamento e formato de erro. Uma rota que
respeite as seis vira tool sem discussão nem adaptador.

---

## 1. Prefixo de path por domínio

```
/admin/<dominio>/<recurso>
```

| Domínio | Prefixo | Situação |
|---|---|---|
| Financeiro | `/admin/finance/...` | existe |
| Reservas | `/admin/reservations/...` | existe (rota de tool ainda a criar) |
| Estoque | `/admin/inventory/...` | futuro |
| Marketing | `/admin/marketing/...` | futuro |

Regras:

1. **Um `APIRouter` por domínio**, com `prefix="/admin/<dominio>"` e `tags=["..."]`, um
   arquivo em `src/api/endpoints/`. Registrar em `main.py`. É só isso que "adicionar um
   domínio" significa.
2. O domínio é **sempre em inglês e no plural** quando for coletivo
   (`reservations`), acompanhando o que já existe. O recurso é **em português**
   (`/resultado`, `/meta`, `/agenda`), porque é o vocabulário da operação e reduz a
   distância entre o que o usuário fala e o que o modelo escolhe.
3. **Só `GET`.** Toda tool é leitura. Escrita (criar reserva, lançar despesa) exige
   confirmação humana e não entra nesta convenção.
4. **Autenticação idêntica em todos os domínios:** `Depends(validate_admin_or_internal)`,
   header `x-api-key: <INTERNAL_API_KEY>`.
5. **Rota de tool não é rota de dashboard.** Onde a rota existente serve ao dashboard e
   ao agente com necessidades diferentes, cria-se uma **rota nova** no mesmo prefixo
   (ex.: `/admin/finance/revenue` fica com o dashboard, `/admin/finance/resultado`
   atende a Júlia). Não se muda o formato de uma rota que o dashboard ou o n8n já
   consomem.

### 1.1 Nome da tool ↔ path

O nome que o modelo vê é `<dominio_pt>_<assunto>`, em `snake_case`:

| Nome da tool | Path |
|---|---|
| `financeiro_resumo_periodo` | `GET /admin/finance/analysis/overview` |
| `financeiro_resultado_periodo` | `GET /admin/finance/resultado` |
| `reservas_agenda` | `GET /admin/reservations/agenda` |
| `estoque_itens_criticos` | `GET /admin/inventory/criticos` |

O prefixo em português (`financeiro_`, `reservas_`, `estoque_`, `marketing_`) existe
para o modelo agrupar por assunto quando houver 15 ou 20 ferramentas na lista.

---

## 2. Nomes de parâmetro — iguais em todos os domínios

### 2.1 Datas

**`start_date` e `end_date`, sempre. Formato `YYYY-MM-DD`, sem exceção.**

Não existe `start`, `from`, `data_inicio`, `dataInicial`, `date`, `mes_referencia` nem
`periodo` como nome de parâmetro em rota nova. O nome é o mesmo nas quatro famílias:
o agente aprende uma vez e acerta em todas.

Implementação obrigatória: `Depends(date_range_params)`, de
`src/api/dependencies/date_range.py`. A dependência já resolve:

- `start_date`/`end_date` canônicos;
- `start`/`end` como **alias depreciado** (marcados `deprecated: true` no OpenAPI),
  existentes só porque `/admin/finance/revenue` foi para produção com eles e o n8n
  ainda os envia. **Rota nova não ganha alias novo** — o alias é dívida, não padrão;
- canônico vence o alias quando os dois vierem;
- `start_date > end_date` → erro `PERIODO_INVALIDO`;
- meio intervalo → erro `PERIODO_INCOMPLETO` nas rotas em que o intervalo é opcional
  (`require_both_or_none()`), em vez de ignorar o filtro em silêncio.

Fuso de referência para "hoje", "ontem", "este mês": **`America/Fortaleza`**, o mesmo
que `AdminFinanceService.FINANCE_ANALYSIS_TIMEZONE` já usa. A resolução de linguagem
natural ("ontem", "semana passada") é responsabilidade do **agente**, que converte para
datas absolutas antes de chamar. A rota nunca interpreta texto de data.

### 2.2 Os outros parâmetros comuns

| Parâmetro | Tipo | Significado | Default |
|---|---|---|---|
| `start_date` / `end_date` | date `YYYY-MM-DD` | intervalo | conforme a rota |
| `limite` | int ≥ 1 | máximo de itens na maior lista da resposta | ver §4 |
| `incluir_<bloco>` | bool | liga/desliga um bloco opcional (`incluir_itens`, `incluir_vendas_por_hora`) | `true` quando a rota também serve ao dashboard |
| `status` | str | filtro de estado, valores enumerados e listados no erro | `null` (todos) |
| `busca` | str | texto livre sobre o campo descritivo do domínio | `null` |

Regras:

1. **Nomes em português nos parâmetros novos** (`limite`, `ambiente`, `categoria`), com
   exceção de `start_date`/`end_date`, que já são o padrão consolidado e cujo custo de
   troca não se justifica.
2. **Entidade se identifica por nome, não por UUID.** O agente tem *"Salão"*, não
   `3f2a…`. Se a rota filtra por entidade, ela aceita o nome (case-insensitive,
   acento-insensitive) e resolve o id internamente. UUID pode ser aceito **também**,
   nunca **apenas**. Isso elimina a chamada encadeada de descoberta, que é onde o
   agente mais erra.
3. **Todo parâmetro novo é opcional com default que preserva o comportamento atual.**
   É o que permite crescer sem quebrar o dashboard nem o n8n.
4. **Nenhum parâmetro de layout.** Não existe `formato`, `ordenar_por`, `pagina`,
   `agrupar_por`. Se a tool precisa disso, a rota está errada: crie outra rota que já
   responda a pergunta.

---

## 3. Envelope de resposta padrão

Toda rota de tool devolve **exatamente** esta estrutura de quatro chaves de topo:

```json
{
  "periodo":     { "start_date": "...", "end_date": "...", "rotulo": "..." },
  "dados":       { },
  "avisos":      [],
  "truncamento": { "truncado": false, "retornados": 0, "total": 0, "sugestao": null }
}
```

| Chave | Tipo | Obrigatória | O que carrega |
|---|---|---|---|
| `periodo` | objeto ou `null` | sim | **O período efetivamente consultado**, não o pedido |
| `periodo.start_date` | date `YYYY-MM-DD` | sim | primeiro dia incluído |
| `periodo.end_date` | date `YYYY-MM-DD` | sim | último dia incluído |
| `periodo.rotulo` | str | sim | período por extenso, pt-BR, pronto para o agente repetir na resposta |
| `dados` | objeto | sim | o conteúdo, com números já calculados |
| `avisos` | lista de str | sim (pode ser `[]`) | frases curtas em pt-BR sobre o que afeta a leitura do número |
| `truncamento` | objeto | sim | ver §4 |

### 3.1 `periodo` — por que "efetivamente consultado"

É a chave que impede a Júlia de afirmar um número sobre o período errado. Se o pedido
foi ajustado (fim de semana sem movimento, dado ainda não carregado pelo ETL, rota que
sempre devolve mês fechado), `periodo` reflete **o que foi somado**, e `avisos` explica
a diferença:

```json
{
  "periodo": {
    "start_date": "2026-08-01",
    "end_date": "2026-08-27",
    "rotulo": "01/08/2026 a 27/08/2026"
  },
  "avisos": ["Você pediu até 31/08, mas só há dados carregados até 27/08."]
}
```

`rotulo` usa a forma que o brasileiro fala: `"hoje"`, `"ontem"`, `"27/08/2026"`,
`"01/08/2026 a 27/08/2026"`, `"agosto/2026"`, `"últimos 7 dias (21/08 a 27/08)"`.

Rota que legitimamente não tem período (ex.: `estoque_itens_criticos`, que é uma foto
do agora) devolve `"periodo": null` — a chave continua presente.

### 3.2 `dados` — números prontos

Regra dura: **quem consome não calcula nada.**

- Percentual, variação, saldo, média, projeção: vêm calculados. Nunca se devolve
  numerador e denominador esperando divisão.
- Dinheiro: `float` em reais, arredondado a 2 casas (`33150.3`). Sem centavos inteiros,
  sem string, sem `"R$ "`.
- Percentual: `float` já em pontos percentuais (`39.31` = 39,31%), sem o sinal `%`.
- Data: `YYYY-MM-DD`. Hora: `HH:MM`. Nada de ISO com fuso dentro de `dados`.
- Ausência de dado é `0` quando há uma soma vazia legítima, e `null` quando o dado não
  existe. Os dois casos ganham uma linha em `avisos`.
- **Nenhum campo de layout**: nada de `key`, `label`, `color`, `icon`, `order`,
  `chart_data`, `sales_by_hour` só para desenhar barra. Se um campo só faz sentido
  dentro de um gráfico, ele não entra na resposta da tool.
- **Nenhum id técnico** que o agente não vá usar: `uuid`, `eye_transaction_id`,
  `comprovante_path`. E **nenhum dado pessoal além do estritamente necessário** — nome
  do cliente quando a pergunta é sobre a reserva dele; e-mail e telefone nunca.

### 3.3 `avisos` — o que muda a leitura do número

Lista de frases curtas, em pt-BR, escritas para o agente **ler em voz alta** se
precisar. Servem para o caso em que o número está certo mas seria mal interpretado
sozinho:

```json
"avisos": [
  "Período inclui 2 dias em que o restaurante esteve fechado.",
  "Despesas de agosto ainda podem receber lançamentos retroativos.",
  "Mostrando as 5 maiores categorias de 11 no total."
]
```

Lista vazia é o normal. Aviso não é log, não é debug e não é erro — se a chamada falhou,
use §5.

---

## 4. Limite de linhas e sinalização de truncamento

**Teto: 50 linhas de JSON identado (`indent=2`) por resposta.** Alvo confortável: 20 a
35. O envelope custa ~15 linhas fixas, então `dados` tem ~35 de orçamento real.

O teto não é estético: uma resposta de 400 linhas custa contexto, atrasa a resposta no
WhatsApp e aumenta a chance de o modelo citar a linha errada. Para calibrar, os números
medidos em `TOOLS.md`: `/analysis/overview` com intervalo cabe em 19 linhas;
`/analysis/products` no default ocupa 425; `/revenue` de um único dia, 4.000.

### 4.1 Como caber

Em ordem de preferência:

1. **Agregue no SQL, não devolva a lista.** "Quanto vendi de chopp?" é um número, não
   412 transações.
2. **Corte a lista por `limite`**, com default pequeno e ordenação por relevância
   (maior valor primeiro), nunca cronológica bruta.
3. **Torne opcional o bloco caro** (`incluir_itens=false`,
   `incluir_vendas_por_hora=false`), com default que preserva o dashboard.
4. **Se ainda não couber, a rota está respondendo à pergunta errada.** Crie outra rota,
   mais fina, que responda direto.

Defaults de `limite` sugeridos: listas de ranking, `5`; listas de eventos (reservas do
dia), `15`; teto absoluto, `50`.

### 4.2 Como sinalizar

O bloco `truncamento` é **sempre presente**, mesmo sem corte:

```json
"truncamento": { "truncado": false, "retornados": 3, "total": 3, "sugestao": null }
```

Quando houve corte:

```json
"truncamento": {
  "truncado": true,
  "retornados": 5,
  "total": 11,
  "sugestao": "Filtre por categoria ou aumente limite (máx 50) para ver as demais."
}
```

| Campo | Tipo | Significado |
|---|---|---|
| `truncado` | bool | houve corte |
| `retornados` | int | itens na maior lista de `dados` |
| `total` | int | itens que existiriam sem `limite` — **contados no banco**, não estimados |
| `sugestao` | str ou `null` | frase em pt-BR dizendo **como** ver o resto |

Duas regras que fazem esse bloco valer:

1. `total` sai de um `COUNT` de verdade. Truncamento silencioso é pior que erro: o
   agente afirma "as despesas foram essas" quando eram só as cinco primeiras.
2. Quando `truncado` é `true`, **`avisos` ganha uma frase** dizendo em português o que
   foi cortado. O modelo lê `avisos` com muito mais confiabilidade do que interpreta um
   booleano solto.

---

## 5. Formato de erro legível

Toda falha devolve este corpo, com o HTTP status correspondente:

```json
{
  "erro": {
    "codigo": "PERIODO_INVALIDO",
    "mensagem": "A data inicial (09/08/2026) é posterior à data final (01/08/2026).",
    "sugestao": "Inverta as datas ou confirme o período com quem perguntou."
  }
}
```

| Campo | Para quem | Regra |
|---|---|---|
| `codigo` | log e código | `SCREAMING_SNAKE_CASE`, estável, nunca muda de significado |
| `mensagem` | o agente | pt-BR, uma frase, **diz o que aconteceu com os valores concretos** |
| `sugestao` | o agente | pt-BR, o que fazer a seguir — outra chamada, ou o que perguntar ao usuário |

A `mensagem` é escrita para ser **quase repetível ao usuário final**. Nada de
`"Could not load finance categories analysis"`, `KeyError`, stack trace, nome de tabela
ou de coluna. O agente precisa conseguir explicar a falha sem inventar a causa.

### 5.1 Catálogo de códigos

| HTTP | `codigo` | Quando |
|---|---|---|
| 400 | `PERIODO_INVALIDO` | `start_date` posterior a `end_date` |
| 400 | `PERIODO_INCOMPLETO` | só um lado do intervalo informado |
| 400 | `PARAMETRO_INVALIDO` | valor fora do enumerado — **a mensagem lista os válidos** |
| 404 | `ENTIDADE_NAO_ENCONTRADA` | nome de ambiente/categoria/item não casou — **a mensagem lista os existentes ou os mais próximos** |
| 401 | `NAO_AUTORIZADO` | `x-api-key` ausente ou inválida |
| 409 | `DADO_INDISPONIVEL` | período pedido ainda não carregado pelo ETL |
| 500 | `ERRO_INTERNO` | falha inesperada — mensagem genérica, detalhe só no log |

Exemplo do caso mais frequente na prática (o agente chutou o nome do ambiente):

```json
{
  "erro": {
    "codigo": "ENTIDADE_NAO_ENCONTRADA",
    "mensagem": "Não existe ambiente chamado 'Terraço'.",
    "sugestao": "Os ambientes disponíveis são: Salão, Varanda, Deck. Confirme qual deles."
  }
}
```

Listar as opções válidas dentro do erro é o que permite o agente se corrigir sozinho na
chamada seguinte, em vez de devolver "não consegui" ao usuário.

### 5.2 Sobre as rotas atuais

As rotas de hoje devolvem o `{"detail": "..."}` padrão do FastAPI. **Elas não mudam** —
o dashboard e o n8n já convivem com esse formato. O envelope de erro vale para **rotas
novas de tool** (`/finance/resultado`, `/finance/meta`, `/reservations/agenda`).

Quando valer a pena unificar, o caminho é um `exception_handler` global em `main.py`
que converta `HTTPException` para o envelope apenas nos paths registrados como tool —
~30 linhas, sem tocar em nenhuma rota. Não é pré-requisito para nada.

---

## 6. Exemplo: como uma rota futura de estoque se encaixa

**Não implementar.** Serve para mostrar que a convenção fecha num domínio que ainda não
existe, sem inventar nada de novo.

Pergunta real no WhatsApp: *"o que tá acabando?"*

### 6.1 A rota

```
GET /admin/inventory/criticos
```

| Parâmetro | Tipo | Obrigatório | Default | Exemplo |
|---|---|---|---|---|
| `categoria` | str (nome, case-insensitive) | não | todas | `Bebidas` |
| `limite` | int (1–50) | não | `10` | `10` |

Sem `start_date`/`end_date`: estoque é uma **foto do agora**, não um intervalo. Por isso
`periodo` vem `null` — e vem, porque a chave é obrigatória.

### 6.2 A resposta (~34 linhas, dentro do teto)

```json
{
  "periodo": null,
  "dados": {
    "itens_criticos": 7,
    "itens": [
      { "item": "Chopp Pilsen 50L", "categoria": "Bebidas",  "saldo": 1.0,  "minimo": 4.0,  "unidade": "barril", "cobertura_dias": 0.8 },
      { "item": "Muçarela",         "categoria": "Insumos",  "saldo": 6.5,  "minimo": 20.0, "unidade": "kg",     "cobertura_dias": 1.2 },
      { "item": "Tomate Italiano",  "categoria": "Hortifrúti","saldo": 8.0, "minimo": 15.0, "unidade": "kg",     "cobertura_dias": 1.5 },
      { "item": "Farinha 00",       "categoria": "Insumos",  "saldo": 25.0, "minimo": 40.0, "unidade": "kg",     "cobertura_dias": 2.1 },
      { "item": "Azeite Extra",     "categoria": "Insumos",  "saldo": 4.0,  "minimo": 6.0,  "unidade": "L",      "cobertura_dias": 3.4 }
    ]
  },
  "avisos": [
    "Mostrando os 5 itens mais críticos de 7 abaixo do mínimo.",
    "Cobertura em dias calculada sobre o consumo médio dos últimos 30 dias."
  ],
  "truncamento": {
    "truncado": true,
    "retornados": 5,
    "total": 7,
    "sugestao": "Aumente limite ou filtre por categoria para ver os demais."
  }
}
```

### 6.3 O que o exemplo demonstra, ponto a ponto

| Regra | Como aparece aqui |
|---|---|
| Prefixo por domínio (§1) | `/admin/inventory/criticos` — router novo, `main.py` ganha uma linha |
| Recurso em pt, domínio em en (§1) | `inventory` + `criticos` |
| Só `GET`, mesma auth (§1) | leitura, `x-api-key` |
| Entidade por nome (§2.2) | `categoria="Bebidas"`, não UUID de categoria |
| `periodo` sempre presente (§3.1) | `null`, porque estoque não tem intervalo |
| Números prontos (§3.2) | `cobertura_dias` já dividido; o agente não recebe consumo e saldo para dividir |
| Sem campo de layout (§3.2) | sem `color`, sem `status_badge`, sem `order` |
| `avisos` explica a leitura (§3.3) | diz sobre que base a cobertura foi calculada |
| Teto de 50 linhas (§4) | 34 linhas com `limite=5` |
| Truncamento explícito (§4.2) | `total: 7` de `COUNT` real + a mesma informação repetida em `avisos` |

### 6.4 O contrato da tool

> **`estoque_itens_criticos`** — Itens de estoque abaixo do nível mínimo, do mais
> crítico para o menos, com saldo atual, mínimo configurado e por quantos dias o saldo
> ainda cobre o consumo médio. Use para "o que tá acabando?", "preciso comprar o quê?",
> "tem chopp suficiente pro fim de semana?". Não use para valor financeiro de estoque —
> esta ferramenta responde em quantidade, não em reais.

Marketing entra pela mesma porta, sem nenhuma decisão nova: `/admin/marketing/campanhas`
com `start_date`/`end_date`, envelope, teto de 50 linhas e o mesmo catálogo de erros.

---

## 7. Checklist antes de publicar uma rota como tool

- [ ] Path é `/admin/<dominio>/<recurso>`, método `GET`, `Depends(validate_admin_or_internal)`.
- [ ] Datas se chamam `start_date`/`end_date` e vêm de `Depends(date_range_params)`.
- [ ] Entidades aceitam **nome**, não só UUID.
- [ ] Todo parâmetro novo é opcional, com default que preserva o comportamento atual.
- [ ] Resposta tem as quatro chaves: `periodo`, `dados`, `avisos`, `truncamento`.
- [ ] `periodo` reflete o que foi **efetivamente** consultado, com `rotulo` em pt-BR.
- [ ] Nenhum número exige cálculo de quem consome.
- [ ] Nenhum campo existe só para desenhar tela; nenhum id técnico; nenhum dado pessoal supérfluo.
- [ ] Resposta cabe em **50 linhas** de `json.dumps(indent=2)` no pior caso realista — medido, não estimado.
- [ ] `truncamento.total` vem de um `COUNT` real, e o corte também está escrito em `avisos`.
- [ ] Erros usam `{"erro": {codigo, mensagem, sugestao}}`, com as opções válidas listadas na mensagem.
- [ ] A descrição da tool diz **quando usar** e, se houver ferramenta parecida, **quando não usar**.
- [ ] A rota reusa service existente ou justifica por que precisou de um método novo.
