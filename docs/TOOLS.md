# TOOLS.md — Auditoria das rotas atuais para uso como ferramentas da Júlia

Data da auditoria: 28/08/2026
Base: código deste repositório (`src/api/endpoints/`, `src/services/`, `src/repositories/`).

> **Nota sobre a auditoria n8n.** Os documentos `docs/ARQUITETURA.md`, `docs/RISCOS.md`
> e `docs/RIGIDEZ.md` citados na tarefa **não existem neste repositório** — a pasta
> `docs/` não estava versionada e nunca apareceu no histórico do git
> (`git log --all --name-only` não retorna nenhum arquivo em `docs/`). Toda a auditoria
> abaixo foi feita a partir do código-fonte. Onde uma afirmação depende de saber o que
> o n8n realmente envia hoje, isso está marcado como **[verificar no n8n]**.

---

## 1. Como as rotas são autenticadas

Todas as rotas de `/admin/*` passam por `validate_admin_or_internal`
(`src/api/dependencies/admin_auth.py`). Dois caminhos aceitos:

| Caminho | Header | Uso |
|---|---|---|
| Chave interna | `x-api-key: <INTERNAL_API_KEY>` | n8n / Júlia |
| JWT de admin | `Authorization: Bearer <token>` | dashboard web |

A camada de ferramentas usa **`x-api-key`**. Sem header válido: `401` com
`{"detail": "Invalid credentials or internal API key"}`.

---

## 2. Inventário das rotas financeiras

Todas sob o prefixo `/admin/finance` (`src/api/endpoints/admin_finance.py`).
As contagens de linhas são do JSON identado (`json.dumps(indent=2)`), medidas com
payloads representativos da operação do restaurante (~120 transações/dia, ~3 itens por
transação, ~8 categorias de despesa).

### 2.1 `GET /admin/finance/revenue`

| | |
|---|---|
| Serviço | `AdminFinanceService.get_revenue` |
| Parâmetros | `start_date` (date, **obrigatório**), `end_date` (date, **obrigatório**), aliases legados `start` / `end` |
| Resposta | `AdminRevenueResponse` |

Campos: `summary{revenue_total, transactions, ticket_average}`, `transactions[]`
(cada uma com 10 campos + lista de `items[]`), `top_products[]` (10),
`sales_by_hour[]`, `sales_by_day[]`, `payment_insights[]`, `start_date`, `end_date`,
`source`.

**Tamanho típico:**

| Intervalo | Linhas |
|---|---|
| 1 dia (~120 transações) | **~4.000** |
| 7 dias (~800 transações) | **~25.800** |
| 30 dias (~3.500 transações) | **~112.300** |
| 1 dia sem o bloco `transactions` | ~159 |

**Serve como tool?** **Não.** Ultrapassa o limite de ~50 linhas em duas ordens de
grandeza já no menor intervalo possível. O bloco `transactions` (com `items`
aninhados) responde por ~96% do volume e não tem valor para uma resposta de WhatsApp.

**Ajuste mínimo proposto** (não implementado — ver §7): manter `/revenue` como rota
**exclusiva do dashboard** e atender a Júlia pela rota fina
`GET /admin/finance/resultado` (§4.1). Se ainda assim se quiser usar `/revenue` como
tool, o ajuste mínimo é um parâmetro `include_transactions: bool = true` — o default
preserva o dashboard e a tool passa `false`, caindo para ~159 linhas (ainda acima do
limite, por causa de `sales_by_hour` + `sales_by_day` + `top_products`).

### 2.2 `GET /admin/finance/expenses`

| | |
|---|---|
| Serviço | `AdminFinanceService.list_expenses` |
| Parâmetros | `start_date`, `end_date` (ambos opcionais, aliases `start`/`end`), `category` (str, normalizada para maiúsculas), `search` (str), `limit` (int ≥1, default 100), `offset` (int ≥0, default 0) |
| Resposta | `AdminExpenseListResponse` |

Campos: `summary{total_expenses, expenses_count, highest_expense, top_category}`,
`by_category[]{category, total, count}`, `items[]{id, descricao, data, valor,
categoria, comprovante_url}`.

**Tamanho típico:**

| Configuração | Linhas |
|---|---|
| default (`limit=100`, 8 categorias) | **~852** |
| `limit=10` | ~132 |
| só `summary` + 8 categorias (`items` vazio) | ~51 |
| só `summary` + 5 categorias | ~36 |

**Serve como tool?** **Quase.** Os números já vêm prontos (total, contagem, maior
despesa, categoria líder, rateio por categoria); o que estoura o limite é a lista
`items`, que a Júlia quase nunca precisa ler item a item.

**Ajuste mínimo proposto:** parâmetro `incluir_itens: bool = true`. O default preserva
o dashboard; a tool chama com `incluir_itens=false` e recebe ~36–51 linhas. Esforço:
~15 linhas (1 parâmetro na rota, 1 no service, um `if` antes de montar `items`).
Alternativa sem código novo: a tool chama com `limit=1` (~59 linhas) — funciona, mas
devolve um item inútil e continua no limite.

### 2.3 `GET /admin/finance/analysis/overview`

| | |
|---|---|
| Serviço | `AdminFinanceService.get_analysis_overview` |
| Parâmetros | `start_date`, `end_date` (opcionais, aliases `start`/`end`) — **novos, ver §3** |
| Resposta | `AdminFinanceAnalysisOverviewResponse` |

Campos por período: `key`, `label`, `start_date`, `end_date`, `revenue_total`,
`expenses_total`, `balance`, `margin_percent`, `transactions`, `ticket_average`,
`expenses_count`, `top_expense_category`.

**Tamanho típico:**

| Configuração | Linhas |
|---|---|
| default (hoje / 7 dias / 30 dias) | **~47** |
| com intervalo informado (1 período `custom`) | **~19** |

**Serve como tool?** **Sim.** É a melhor rota financeira que já existe: dentro do
limite, números prontos (inclusive `balance` e `margin_percent` já calculados) e sem
campo nenhum de layout. É a base do contrato `financeiro_resumo_periodo` (§6.1).

### 2.4 `GET /admin/finance/analysis/categories`

| | |
|---|---|
| Serviço | `AdminFinanceService.get_categories_analysis` |
| Parâmetros | `start_date`, `end_date` (opcionais, aliases `start`/`end`) — **novos, ver §3** |
| Resposta | `CategoriesAnalysisResponse` |

Campos por período: `key`, `label`, `start_date`, `end_date`, `total_expenses`,
`expenses_by_category[]{category, total, count, percentage}`.

**Tamanho típico:**

| Configuração | Linhas |
|---|---|
| default (3 períodos × 8 categorias) | **~176** |
| com intervalo (1 período × 8 categorias) | ~62 |
| com intervalo (1 período × 5 categorias) | ~44 |

**Serve como tool?** **Sim, com intervalo informado e ressalva.** O `percentage` já vem
calculado, que é exatamente o que se quer. Com o default de 3 períodos, estoura o
limite.

**Ajuste mínimo proposto:** parâmetro `limite_categorias: int = 0` (0 = todas). A tool
chama com `limite_categorias=5` e fica em ~44 linhas; o dashboard não passa nada e nada
muda. Esforço: ~10 linhas (slice na lista, que o repositório já devolve ordenada por
total desc). Como o restaurante hoje tem poucas categorias, na prática 1 período já
cabe — o parâmetro é seguro contra o crescimento do plano de contas.

### 2.5 `GET /admin/finance/analysis/products`

| | |
|---|---|
| Serviço | `AdminFinanceService.get_products_analysis` |
| Parâmetros | `start_date`, `end_date` (opcionais, aliases `start`/`end`) — **novos, ver §3** |
| Resposta | `ProductsAnalysisResponse` |

Campos por período: `key`, `label`, `start_date`, `end_date`,
`top_products[]{product_name, quantity, revenue, average_price}` (10 fixos),
`sales_by_hour[]{hour, revenue, transactions}`.

**Tamanho típico:**

| Configuração | Linhas |
|---|---|
| default (3 períodos) | **~425** |
| com intervalo (1 período, 10 produtos + horas) | ~145 |
| com intervalo (5 produtos + horas) | ~115 |
| com intervalo (5 produtos, sem `sales_by_hour`) | **~44** |

**Serve como tool?** **Não sem ajuste.** `sales_by_hour` é o caso mais claro de campo
de layout: existe para desenhar o gráfico de barras por hora do dashboard. Numa
resposta de WhatsApp ele é ruído, e sozinho custa ~70 linhas.

**Ajuste mínimo proposto:** dois parâmetros — `limite_produtos: int = 10` e
`incluir_vendas_por_hora: bool = true`. A tool chama com `limite_produtos=5` e
`incluir_vendas_por_hora=false` → ~44 linhas. Defaults preservam o dashboard.
Esforço: ~20 linhas (rota + service + 2 condicionais no builder do período).

---

## 3. Padronização dos nomes de parâmetro de data — **implementado**

**Padrão escolhido: `start_date` / `end_date`.** Motivos: já era o nome usado por
`/expenses`, é o nome interno de todos os services e repositórios
(`get_revenue(start_date=…, end_date=…)`), e é autoexplicativo para o modelo que lê a
descrição da tool. `start`/`end` continuam funcionando como **alias depreciado**.

Implementação: `src/api/dependencies/date_range.py`, uma dependência única
(`date_range_params`) aplicada às cinco rotas financeiras.

Regras de resolução:

1. Se `start_date`/`end_date` vierem, valem. Se vierem só `start`/`end`, são aceitos.
2. Se os dois pares vierem juntos, **o canônico vence** e o legado é ignorado.
3. `start_date > end_date` → `400 {"detail": "start_date deve ser anterior ou igual a end_date."}`.
4. Em `/revenue` o intervalo continua **obrigatório**; faltando, `400 {"detail": "Informe start_date e end_date no formato YYYY-MM-DD."}` (antes era o `422` genérico do FastAPI).
5. Nas três rotas `/analysis/*` o intervalo é **opcional**, mas **não pode vir pela metade** — meio intervalo devolve `400` com explicação, em vez de ignorar o filtro em silêncio.
6. Em `/expenses` o comportamento antigo foi **preservado integralmente**: `start_date` sozinho continua válido (filtra só o limite inferior), porque o repositório já trata cada lado como opcional independente e o n8n pode estar usando assim hoje **[verificar no n8n]**.

Os aliases aparecem no OpenAPI com `deprecated: true`, então o Swagger já sinaliza a
migração sem quebrar ninguém.

Verificação executada (com o service mockado, sem banco):

```
legacy start/end      -> 200  (2026-08-01, 2026-08-07)
canonical start_date  -> 200  (2026-08-01, 2026-08-07)
canonical vence alias -> 200  (2026-08-05, 2026-08-07)
sem datas em /revenue -> 400  "Informe start_date e end_date no formato YYYY-MM-DD."
datas invertidas      -> 400  "start_date deve ser anterior ou igual a end_date."
overview sem datas    -> 200  ['today', 'last_7_days', 'last_30_days']
overview com datas    -> 200  [('custom', '2026-08-01', '2026-08-07')]
overview meio período -> 400  "Informe start_date e end_date juntos, ou nenhum dos dois..."
expenses só start_date-> 200  (2026-08-01, None)   # compatibilidade preservada
sem x-api-key         -> 401
```

### 3.1 Intervalo opcional em `/analysis/*` — **implementado**

`_analysis_period_definitions(start_date, end_date)` passou a ser o único ponto de
decisão: sem datas, devolve os três períodos de sempre (`today`, `last_7_days`,
`last_30_days`, no fuso `America/Fortaleza`); com datas, devolve **um único período**
com `key="custom"` e `label="Período personalizado"`.

O formato da resposta **não muda** — continua sendo
`{"periods": [...], "source": "database"}`, só que com um elemento. Nenhum consumidor
que itera sobre `periods` quebra. As três rotas (`overview`, `categories`, `products`)
herdam isso de graça, porque as três já usavam esse mesmo helper.

---

## 4. Estimativa das duas rotas finas (não implementadas)

### 4.1 `GET /admin/finance/resultado` — resultado do período com comparativo

Receita menos despesa no período pedido, mais o mesmo cálculo para o período anterior
de igual duração e a variação percentual entre os dois.

**Reuso:** total. `AdminFinanceService._build_analysis_period()` já devolve exatamente
`revenue_total`, `expenses_total`, `balance`, `margin_percent`, `transactions` e
`ticket_average` para um par de datas arbitrário. A rota chama esse método duas vezes
(período pedido e período anterior) e divide. **Nenhuma query nova, nenhum repositório
novo, nenhum modelo novo.**

Cálculo do período anterior: `duracao = (end_date - start_date).days + 1`;
`anterior_end = start_date - 1 dia`; `anterior_start = anterior_end - (duracao - 1)`.

| Item | Esforço |
|---|---|
| Schema `ResultadoPeriodoResponse` (envelope + comparativo) | ~35 linhas |
| Método `get_resultado_periodo()` no service | ~40 linhas |
| Rota | ~25 linhas |
| **Total** | **~100 linhas, 1 schema novo + 2 arquivos editados. Meio dia com teste manual.** |

Tamanho da resposta: **~33 linhas**. Dentro do limite.

**Risco:** baixo. Rota nova, nenhum consumidor existente afetado.

### 4.2 `GET /admin/finance/meta` — meta do mês

Hoje a tabela `metas_mensais` é lida **direto pelo n8n**, sem passar pelo backend.
Confirmado: `grep -rin "meta" src/` não retorna **nenhuma** ocorrência — não existe
modelo, repositório, schema nem rota. É a única das cinco estimativas que exige código
de acesso a dados novo.

**Não reusa quase nada** da camada financeira atual, exceto
`FinanceRepository.get_revenue_summary()` para a receita realizada do mês — que é
justamente o número que torna a rota útil (a meta sozinha o n8n já tem; o que falta é
meta *versus* realizado, calculado no mesmo lugar e com a mesma regra de
`transaction_type = '0'` que o resto do financeiro usa).

**[verificar no n8n]** o schema e as colunas reais de `metas_mensais`. A estimativa
abaixo assume algo como `(mes date | ano int + mes int, valor_meta numeric)` no schema
`giardini_financeiro`.

| Item | Esforço |
|---|---|
| Modelo `MonthlyGoal` (`metas_mensais`) | ~25 linhas |
| `GoalRepository.get_by_month()` | ~20 linhas |
| Método `get_meta_do_mes()` no service (meta, realizado, % atingido, falta, projeção) | ~45 linhas |
| Schema + rota | ~45 linhas |
| **Total** | **~135 linhas, 3 arquivos novos + 2 editados. Um dia, incluindo confirmar o schema da tabela.** |

Tamanho da resposta: **~25 linhas**. Dentro do limite.

**Risco:** baixo no backend. O ponto de atenção é que o n8n continuará lendo a tabela
direto até ser migrado — os dois caminhos coexistem sem conflito, mas a regra de
cálculo do "realizado" precisa ser a mesma nos dois lados enquanto durar a
duplicidade, senão a Júlia e o dashboard divergem no mesmo dia.

---

## 5. Reservas: existe rota consumível por data e ambiente?

**Existe, parcialmente:** `GET /admin/reservations`
(`src/api/endpoints/admin_reservations.py`, prefixo `/admin`).

| | |
|---|---|
| Serviço | `AdminReservationService.list_reservations` |
| Parâmetros | `date` (date, alias de `reservation_date`), `environment_id` (**UUID**), `period` (`all`\|`today`\|`tomorrow`\|`upcoming`, default `all`), `status` (`confirmed`\|`cancelled`\|`completed`\|`no_show`), `search` (str), `limit` (default 100), `offset` (default 0) |
| Resposta | `AdminReservationListResponse`: `summary{total_reservations, today_reservations, total_guests, upcoming_reservations}` + `items[]` com 14 campos cada |

**Tamanho típico:**

| Configuração | Linhas |
|---|---|
| default (`limit=100`) | **~1.610** |
| 20 reservas | **~330** |

**Filtra por data?** Sim, mas **só data única** — não há intervalo. E o parâmetro se
chama `date`, fora do padrão `start_date`/`end_date` fixado em §3.

**Filtra por ambiente?** Sim, mas **só por UUID**. A Júlia recebe *"tem reserva no Salão
amanhã?"* — ela tem o **nome** do ambiente, não o UUID. Hoje seriam duas chamadas
(`GET /environments` para descobrir o UUID, depois `/admin/reservations`), que é
exatamente o tipo de encadeamento que faz o agente errar.

**Serve como tool?** **Não sem ajuste.** Três problemas: volume (~1.610 linhas no
default), ambiente só por UUID, e `items[]` carregando `client_email`, `client_id`,
`environment_id`, `created_at` e `environment_max_capacity` — campos de tabela de
dashboard, não de resposta de WhatsApp. É também o único ponto do inventário com **dado
pessoal** (nome, e-mail e telefone do cliente) indo para o contexto do modelo.

**Ajuste mínimo proposto** (estimativa; não implementado):

| Item | Esforço |
|---|---|
| Aceitar `start_date`/`end_date` além de `date` (o repositório já filtra por `reservation_date`; vira um `between`) | ~20 linhas |
| Aceitar `ambiente` (nome, case-insensitive) resolvido via `EnvironmentRepository`, com erro legível listando os ambientes válidos quando não casar | ~30 linhas |
| Resposta enxuta: `summary` + itens só com `hora`, `pessoas`, `status`, `cliente`, `ambiente` + truncamento | ~40 linhas |
| **Total** | **~90 linhas, 3 arquivos editados. Meio dia.** |

Com 5 campos por item e `limite=15`, a resposta fica em **~40 linhas**.

Recomendação: fazer isso como **rota nova** `GET /admin/reservations/agenda`, não como
mudança na `/admin/reservations` — o dashboard depende do formato atual, e o domínio de
reservas é o próximo a entrar na Júlia. Sobre os dados pessoais: `client_name` basta
para a assistente; e-mail e telefone não devem entrar no contexto do modelo.

---

## 6. Contratos finais das tools

Nomes em `snake_case` com prefixo de domínio, para que o modelo consiga agrupar por
assunto quando as quatro famílias existirem. Descrições em português — é o texto que o
modelo lê para escolher a ferramenta, então cada uma diz **quando usar** e, quando há
risco de confusão com outra, **quando não usar**.

Estado: ✅ = funciona hoje, sem código novo. 🔧 = precisa do ajuste mínimo da seção
indicada. 🆕 = rota nova estimada.

---

### 6.1 ✅ `financeiro_resumo_periodo`

> **Descrição para o modelo:** Resumo financeiro consolidado de um período: faturamento
> total, total de despesas, saldo (receita menos despesa), margem percentual, número de
> transações, ticket médio e a categoria de despesa que mais pesou. Use para perguntas
> como "como foi o movimento hoje?", "quanto faturamos essa semana?", "estamos no azul
> esse mês?". Sem datas, devolve três períodos prontos de uma vez (hoje, últimos 7 dias
> e últimos 30 dias) — é a forma mais barata de responder "e aí, como estamos?".

**Rota:** `GET /admin/finance/analysis/overview`

| Parâmetro | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| `start_date` | date `YYYY-MM-DD` | não | `2026-08-01` |
| `end_date` | date `YYYY-MM-DD` | não | `2026-08-27` |

Os dois juntos ou nenhum.

**Exemplo de resposta real (com intervalo, ~19 linhas):**

```json
{
  "periods": [
    {
      "key": "custom",
      "label": "Período personalizado",
      "start_date": "2026-08-01",
      "end_date": "2026-08-27",
      "revenue_total": 84320.5,
      "expenses_total": 51170.2,
      "balance": 33150.3,
      "margin_percent": 39.31,
      "transactions": 1842,
      "ticket_average": 45.78,
      "expenses_count": 63,
      "top_expense_category": "INSUMOS"
    }
  ],
  "source": "database"
}
```

Sem `start_date`/`end_date`, o array traz três elementos (`today`, `last_7_days`,
`last_30_days`), ~47 linhas.

---

### 6.2 🔧 `financeiro_despesas_por_categoria`

> **Descrição para o modelo:** Quebra das despesas por categoria em um período, com
> valor, quantidade de lançamentos e percentual de cada categoria sobre o total. Use
> para "com o que a gente mais gastou?", "quanto foi de insumos esse mês?", "onde dá
> para cortar?". Não use para o total geral de despesas — para isso,
> `financeiro_resumo_periodo` já basta e é mais barata.

**Rota:** `GET /admin/finance/analysis/categories`

| Parâmetro | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| `start_date` | date `YYYY-MM-DD` | não | `2026-08-01` |
| `end_date` | date `YYYY-MM-DD` | não | `2026-08-27` |
| `limite_categorias` 🔧 | int | não (default: todas) | `5` |

**Exemplo de resposta real (~44 linhas com `limite_categorias=5`):**

```json
{
  "periods": [
    {
      "key": "custom",
      "label": "Período personalizado",
      "start_date": "2026-08-01",
      "end_date": "2026-08-27",
      "total_expenses": 51170.2,
      "expenses_by_category": [
        { "category": "INSUMOS",    "total": 24310.0, "count": 21, "percentage": 47.51 },
        { "category": "PESSOAL",    "total": 14200.0, "count": 8,  "percentage": 27.75 },
        { "category": "ALUGUEL",    "total": 6500.0,  "count": 1,  "percentage": 12.70 },
        { "category": "UTILIDADES", "total": 3980.2,  "count": 6,  "percentage": 7.78 },
        { "category": "MANUTENCAO", "total": 2180.0,  "count": 4,  "percentage": 4.26 }
      ]
    }
  ],
  "source": "database"
}
```

🔧 Sem `limite_categorias` e sem intervalo: ~176 linhas — acima do limite. Ver §2.4.

---

### 6.3 🔧 `financeiro_produtos_mais_vendidos`

> **Descrição para o modelo:** Ranking dos produtos mais vendidos no período, com
> quantidade, faturamento e preço médio de cada um. Use para "o que mais saiu?", "qual o
> carro-chefe?", "quantos chopes vendemos no fim de semana?". Opcionalmente devolve
> também a distribuição de vendas por hora do dia — peça isso apenas quando a pergunta
> for sobre horário de pico.

**Rota:** `GET /admin/finance/analysis/products`

| Parâmetro | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| `start_date` | date `YYYY-MM-DD` | não | `2026-08-22` |
| `end_date` | date `YYYY-MM-DD` | não | `2026-08-24` |
| `limite_produtos` 🔧 | int | não (default `10`) | `5` |
| `incluir_vendas_por_hora` 🔧 | bool | não (default `true`) | `false` |

**Exemplo de resposta real (~44 linhas com `limite_produtos=5` e
`incluir_vendas_por_hora=false`):**

```json
{
  "periods": [
    {
      "key": "custom",
      "label": "Período personalizado",
      "start_date": "2026-08-22",
      "end_date": "2026-08-24",
      "top_products": [
        { "product_name": "Pizza Margherita",  "quantity": 148.0, "revenue": 8880.0, "average_price": 60.0 },
        { "product_name": "Chopp 500ml",       "quantity": 412.0, "revenue": 6180.0, "average_price": 15.0 },
        { "product_name": "Risoto de Camarão", "quantity": 61.0,  "revenue": 4880.0, "average_price": 80.0 },
        { "product_name": "Petit Gateau",      "quantity": 96.0,  "revenue": 2880.0, "average_price": 30.0 },
        { "product_name": "Suco Natural",      "quantity": 173.0, "revenue": 2076.0, "average_price": 12.0 }
      ],
      "sales_by_hour": []
    }
  ],
  "source": "database"
}
```

🔧 Sem os ajustes e sem intervalo: ~425 linhas. Ver §2.5.

---

### 6.4 🔧 `financeiro_despesas_resumo`

> **Descrição para o modelo:** Total gasto no período, quantidade de lançamentos, maior
> despesa individual e a categoria líder — com filtro opcional por categoria ou por
> texto na descrição. Use para "quanto saiu de caixa esse mês?", "qual foi a maior
> despesa?", "quanto pagamos de aluguel?". Para o rateio completo por categoria,
> prefira `financeiro_despesas_por_categoria`.

**Rota:** `GET /admin/finance/expenses`

| Parâmetro | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| `start_date` | date `YYYY-MM-DD` | não | `2026-08-01` |
| `end_date` | date `YYYY-MM-DD` | não | `2026-08-27` |
| `category` | str (normalizada para maiúsculas) | não | `INSUMOS` |
| `search` | str | não | `energia` |
| `incluir_itens` 🔧 | bool | não (default `true`) | `false` |

**Exemplo de resposta real (~36 linhas com `incluir_itens=false`):**

```json
{
  "summary": {
    "total_expenses": 51170.2,
    "expenses_count": 63,
    "highest_expense": 6500.0,
    "top_category": "INSUMOS"
  },
  "by_category": [
    { "category": "INSUMOS",    "total": 24310.0, "count": 21 },
    { "category": "PESSOAL",    "total": 14200.0, "count": 8 },
    { "category": "ALUGUEL",    "total": 6500.0,  "count": 1 },
    { "category": "UTILIDADES", "total": 3980.2,  "count": 6 },
    { "category": "MANUTENCAO", "total": 2180.0,  "count": 4 }
  ],
  "items": []
}
```

🔧 Sem `incluir_itens`: ~852 linhas no default. Ver §2.2.

---

### 6.5 🆕 `financeiro_resultado_periodo`

> **Descrição para o modelo:** Resultado do período — receita menos despesa — comparado
> com o período anterior de mesma duração, com a variação percentual entre os dois. Use
> quando a pergunta tiver comparação no meio: "melhoramos em relação ao mês passado?",
> "essa semana foi melhor que a anterior?", "estamos crescendo?". Para o número do
> período isolado, sem comparação, use `financeiro_resumo_periodo`.

**Rota:** `GET /admin/finance/resultado` — 🆕 estimada em §4.1 (~100 linhas de código).

| Parâmetro | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| `start_date` | date `YYYY-MM-DD` | sim | `2026-08-01` |
| `end_date` | date `YYYY-MM-DD` | sim | `2026-08-27` |

**Exemplo de resposta proposta (~33 linhas, já no envelope de
`CONVENCAO_TOOLS.md`):**

```json
{
  "periodo": {
    "start_date": "2026-08-01",
    "end_date": "2026-08-27",
    "rotulo": "01/08/2026 a 27/08/2026"
  },
  "dados": {
    "receita_total": 84320.5,
    "despesa_total": 51170.2,
    "resultado": 33150.3,
    "margem_percentual": 39.31,
    "transacoes": 1842,
    "ticket_medio": 45.78,
    "comparativo": {
      "periodo_anterior": { "start_date": "2026-07-05", "end_date": "2026-07-31" },
      "receita_total": 79100.0,
      "despesa_total": 49880.0,
      "resultado": 29220.0,
      "variacao_receita_percentual": 6.6,
      "variacao_resultado_percentual": 13.45
    }
  },
  "avisos": [],
  "truncamento": { "truncado": false, "retornados": 1, "total": 1, "sugestao": null }
}
```

---

### 6.6 🆕 `financeiro_meta_do_mes`

> **Descrição para o modelo:** Meta de faturamento do mês e quanto já foi realizado, com
> percentual atingido, quanto falta, média diária necessária para bater a meta e a
> projeção de fechamento no ritmo atual. Use para "estamos batendo a meta?", "quanto
> falta pra meta?", "vamos fechar o mês no azul?". Sempre devolve o mês inteiro — não
> aceita intervalo arbitrário.

**Rota:** `GET /admin/finance/meta` — 🆕 estimada em §4.2 (~135 linhas de código).

| Parâmetro | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| `mes` | str `YYYY-MM` | não (default: mês corrente em `America/Fortaleza`) | `2026-08` |

**Exemplo de resposta proposta (~25 linhas):**

```json
{
  "periodo": {
    "start_date": "2026-08-01",
    "end_date": "2026-08-31",
    "rotulo": "agosto/2026"
  },
  "dados": {
    "mes": "2026-08",
    "meta_receita": 95000.0,
    "receita_realizada": 84320.5,
    "percentual_atingido": 88.76,
    "falta_para_meta": 10679.5,
    "dias_decorridos": 27,
    "dias_restantes": 4,
    "media_diaria_necessaria": 2669.88,
    "projecao_fim_mes": 96812.8
  },
  "avisos": [],
  "truncamento": { "truncado": false, "retornados": 1, "total": 1, "sugestao": null }
}
```

---

### 6.7 🆕 `reservas_agenda`

> **Descrição para o modelo:** Reservas de um dia ou de um intervalo, opcionalmente
> filtradas por ambiente (pelo nome) e por status. Devolve horário, número de pessoas,
> status, nome do cliente e ambiente, além dos totais de reservas e de pessoas
> esperadas. Use para "quantas reservas tem hoje?", "tem mesa no Salão amanhã à noite?",
> "quantas pessoas esperamos no sábado?".

**Rota:** `GET /admin/reservations/agenda` — 🆕 estimada em §5 (~90 linhas de código).
Enquanto não existir, `GET /admin/reservations?date=…` responde, mas fora do padrão e
com ~1.610 linhas no default.

| Parâmetro | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| `start_date` | date `YYYY-MM-DD` | não (default: hoje) | `2026-08-29` |
| `end_date` | date `YYYY-MM-DD` | não (default: igual a `start_date`) | `2026-08-29` |
| `ambiente` | str (nome, case-insensitive) | não | `Salão` |
| `status` | `confirmed`\|`cancelled`\|`completed`\|`no_show` | não | `confirmed` |
| `limite` | int | não (default `15`, máx `50`) | `15` |

**Exemplo de resposta proposta (~40 linhas com 5 reservas):**

```json
{
  "periodo": {
    "start_date": "2026-08-29",
    "end_date": "2026-08-29",
    "rotulo": "29/08/2026 (amanhã)"
  },
  "dados": {
    "total_reservas": 12,
    "total_pessoas": 47,
    "reservas": [
      { "hora": "19:00", "pessoas": 4, "status": "confirmed", "cliente": "Marina Alves",  "ambiente": "Salão" },
      { "hora": "19:30", "pessoas": 2, "status": "confirmed", "cliente": "Rafael Nunes",  "ambiente": "Varanda" },
      { "hora": "20:00", "pessoas": 6, "status": "confirmed", "cliente": "Bruno Tavares", "ambiente": "Salão" },
      { "hora": "20:00", "pessoas": 2, "status": "no_show",   "cliente": "Clara Dias",    "ambiente": "Deck" },
      { "hora": "20:30", "pessoas": 5, "status": "confirmed", "cliente": "Helena Prado",  "ambiente": "Salão" }
    ]
  },
  "avisos": ["Mostrando as 5 primeiras de 12 reservas, ordenadas por horário."],
  "truncamento": {
    "truncado": true,
    "retornados": 5,
    "total": 12,
    "sugestao": "Filtre por ambiente ou aumente limite para ver as demais."
  }
}
```

---

## 7. Resumo: o que serve como tool hoje

| Rota | Linhas (default) | Linhas (ajustada) | Serve? | Ação |
|---|---|---|---|---|
| `/admin/finance/analysis/overview` | ~47 | ~19 | ✅ Sim | Nenhuma |
| `/admin/finance/analysis/categories` | ~176 | ~44 | 🔧 Com ajuste | `limite_categorias` (~10 linhas) |
| `/admin/finance/analysis/products` | ~425 | ~44 | 🔧 Com ajuste | `limite_produtos` + `incluir_vendas_por_hora` (~20 linhas) |
| `/admin/finance/expenses` | ~852 | ~36 | 🔧 Com ajuste | `incluir_itens` (~15 linhas) |
| `/admin/finance/revenue` | ~4.000 a ~112.300 | — | ❌ Não | Manter só para o dashboard; a tool usa `/finance/resultado` |
| `/admin/reservations` | ~1.610 | ~40 | 🔧 Com ajuste | Rota nova `/reservations/agenda` (~90 linhas) |
| `/admin/finance/resultado` | — | ~33 | 🆕 Estimada | ~100 linhas |
| `/admin/finance/meta` | — | ~25 | 🆕 Estimada | ~135 linhas |

**Esforço total do que falta: ~370 linhas de código, tudo por adição — 3 rotas novas e
4 parâmetros opcionais cujo default preserva o comportamento atual. Nenhum service
novo, nenhuma fila, nenhum orquestrador. Um a dois dias de trabalho.**
