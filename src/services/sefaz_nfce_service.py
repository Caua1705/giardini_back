"""Consulta da NFC-e na SEFAZ-CE a partir do conteúdo do QR code.

**Sem navegador.** A página `ShowNFCe.html` é uma casca AngularJS de 1,2 KB: o
controller `ShowNFCeCtrl` quebra o parâmetro `p` do QR, monta um POST e injeta
em `#content` o fragmento que a resposta traz em `data.xml`. Quem faz o mesmo
POST recebe o mesmo fragmento — medido, 14 KB em ~1,2 s.

Isso dispensa Playwright e o Chromium junto: nenhum pacote apt, nenhuma imagem
de 1 GB, nenhum pico de 400 MB de RAM por nota numa VPS de 7,8 GB. A conclusão
de que "a página exige JavaScript" era verdadeira sobre a *página* e falsa sobre
o *dado*.

Os quatro formatos de QR estão em `/js/app.js` do próprio portal, e todos os
quatro estão implementados aqui. Ambiente 1 é produção, 2 é homologação.

**Isto é específico do Ceará.** Outra UF tem outro portal e outro endpoint; o
que sobrevive é a chave de 44 dígitos.

A conferência aritmética vale igual à do PDF: fonte oficial ou não, o que
quebra na leitura é o parser, e nesse caso ele tem que falhar alto em vez de
registrar estoque com número errado.
"""
import html
import json
import re
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation

TEMPO_LIMITE = 30

# O portal recusa requisição sem User-Agent de navegador.
CABECALHOS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

HOSTS = {"1": "nfce.sefaz.ce.gov.br", "2": "nfceh.sefaz.ce.gov.br"}

# --- o fragmento vem de um XSLT, com classes nomeadas e estáveis -------------
# Regex e não parser de árvore de propósito: é markup gerado por folha de
# estilo, os nomes de classe não mudam entre notas, e não vale uma dependência
# nova. O que protege contra o regex derrapar não é o regex — é a conta.
#
# `A` é a aspa do atributo, e aceita as duas: a resposta crua da API vem com
# aspa simples e o navegador normaliza para dupla. Um parser que só entende uma
# delas funciona contra o arquivo salvo e falha contra a SEFAZ de verdade — foi
# exatamente o que aconteceu na primeira versão deste módulo.
A = r"[\"']"

_ITEM = re.compile(
    rf'<tr\s+id={A}Item\s*\+\s*(?P<ordem>\d+){A}.*?'
    rf'<span class={A}txtTit{A}>(?P<descricao>.*?)</span>.*?'
    rf'(?:<span class={A}RCod{A}>\(C[oó]digo:\s*(?P<codigo>[^)]*)\)</span>.*?)?'
    rf'<span class={A}Rqtd{A}>.*?</strong>(?P<qtd>[\d.,]+)</span>.*?'
    rf'<span class={A}RUN{A}>.*?</strong>\s*(?P<unidade>[^<]*)</span>.*?'
    rf'<span class={A}RvlUnit{A}>.*?</strong>(?P<unitario>.*?)</span>.*?'
    rf'<span class={A}valor{A}>(?P<total>[\d.,]+)</span>',
    re.S | re.I,
)
_CHAVE = re.compile(rf'<span class={A}chave{A}>([\d\s]+)</span>', re.I)
_EMITENTE = re.compile(rf'<div class={A}txtTopo{A}[^>]*>(.*?)</div>', re.S | re.I)
_CNPJ = re.compile(r"CNPJ:\s*([\d./-]+)", re.I)
_NUMERO = re.compile(r"N[uú]mero:\s*</strong>\s*(\d+)", re.I)
_SERIE = re.compile(r"S[eé]rie:\s*</strong>\s*(\d+)", re.I)
_EMISSAO = re.compile(
    r"Emiss[aã]o:\s*</strong>\s*(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2}):(\d{2})",
    re.I,
)
_TOTAL = re.compile(
    r"Valor a pagar\s*R\$:?\s*</label>\s*<span[^>]*>([\d.,]+)</span>", re.I
)
_QTD_ITENS = re.compile(
    r"Qtd\.\s*total de itens:?\s*</label>\s*<span[^>]*>(\d+)</span>", re.I
)
_DESCONTO = re.compile(r"Desconto[s]?\s*</label>\s*<span[^>]*>([\d.,]+)</span>", re.I)


class ConsultaInvalida(ValueError):
    """QR que não é NFC-e do Ceará, ou em formato que o portal não reconhece."""


class SefazIndisponivel(RuntimeError):
    """O portal não respondeu, ou respondeu erro."""


def monta_requisicao(conteudo_qr: str) -> tuple[str, dict]:
    """URL e corpo do POST, a partir do conteúdo do QR.

    Os quatro formatos são os do `/js/app.js` do portal.
    """
    if not conteudo_qr or "=" not in conteudo_qr:
        raise ConsultaInvalida("o QR não parece uma consulta de NFC-e")

    if "nVersao=100" in conteudo_qr:
        campos = dict(
            re.findall(r"([^?=&]+)=([^&]*)", conteudo_qr.split("?", 1)[-1])
        )
        corpo = {
            k: campos.get(k)
            for k in ("chNFe", "nVersao", "tpAmb", "cDest", "dhEmi", "vNF",
                      "vICMS", "digVal", "cIdToken", "cHashQRCode")
        }
        ambiente = corpo.get("tpAmb")
        caminho = "/nfce/api/notasFiscal/qrcode/"
        return _url(ambiente, caminho), corpo

    bruto = conteudo_qr[conteudo_qr.index("=") + 1:].replace("%7C", "|")
    partes = bruto.split("|")
    if len(partes) < 3 or not re.fullmatch(r"\d{44}", partes[0]):
        raise ConsultaInvalida("o QR não traz uma chave de acesso de 44 dígitos")

    versao = partes[1]

    if versao == "2":
        # O dígito 35 da chave decide o formato: '9' traz os campos de
        # emissão e valor junto; o resto vem só com CSC e hash.
        if partes[0][34:35] == "9":
            nomes = ("chave_acesso", "versao_qrcode", "tipo_ambiente",
                     "dia_data_emissao", "valor_total_nfce", "digVal",
                     "identificador_csc", "codigo_hash")
        else:
            nomes = ("chave_acesso", "versao_qrcode", "tipo_ambiente",
                     "identificador_csc", "codigo_hash")
        caminho = "/nfce/api/notasFiscal/qrcodev2/"
    elif versao == "3":
        nomes = ("chave_acesso", "versao_qrcode", "tipo_ambiente")
        caminho = "/nfce/api/notasFiscal/qrcodev3/"
    else:
        raise ConsultaInvalida("versão de QR não suportada: %r" % versao)

    corpo = {nome: partes[i] for i, nome in enumerate(nomes) if i < len(partes)}
    return _url(corpo.get("tipo_ambiente"), caminho), corpo


def _url(ambiente: str | None, caminho: str) -> str:
    host = HOSTS.get(str(ambiente or ""))
    if not host:
        raise ConsultaInvalida("ambiente do QR não reconhecido: %r" % ambiente)
    # `http` e nao `https` porque o endpoint nao serve TLS: o handshake morre em
    # SSLV3_ALERT_HANDSHAKE_FAILURE. E o mesmo esquema que o portal usa, e o QR
    # impresso no cupom tambem e http. O que trafega em claro e a chave da nota
    # e o hash do CSC -- os dois ja estao impressos no papel.
    return "http://" + host + caminho


def consulta(conteudo_qr: str) -> str:
    """O fragmento HTML que o portal devolve para esta nota."""
    url, corpo = monta_requisicao(conteudo_qr)
    requisicao = urllib.request.Request(
        url, data=json.dumps(corpo).encode(), method="POST"
    )
    for chave, valor in CABECALHOS.items():
        requisicao.add_header(chave, valor)

    try:
        with urllib.request.urlopen(requisicao, timeout=TEMPO_LIMITE) as resposta:
            dados = json.loads(resposta.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as erro:
        raise SefazIndisponivel("a SEFAZ respondeu %s" % erro.code) from erro
    except Exception as erro:
        raise SefazIndisponivel("não consegui falar com a SEFAZ") from erro

    if dados.get("erro"):
        raise ConsultaInvalida(_texto(str(dados["erro"]))[:200])

    fragmento = dados.get("xml") or ""
    if not fragmento.strip():
        raise SefazIndisponivel("a SEFAZ respondeu sem conteúdo")
    return fragmento


# ------------------------------------------------------------------ parser ---

def _texto(bruto: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", bruto))).strip()


def _numero(bruto: str | None) -> Decimal | None:
    if bruto is None:
        return None
    limpo = _texto(bruto).replace(".", "").replace(",", ".")
    try:
        return Decimal(limpo)
    except (InvalidOperation, ValueError):
        return None


def _centavos(valor: Decimal) -> int:
    return int((valor * 100).quantize(Decimal("1")))


def parse_fragmento(fragmento: str) -> dict:
    """Fragmento da SEFAZ para a mesma estrutura que o `le_nota` produz.

    Os dois caminhos — PDF com texto e foto com QR — desembocam no mesmo
    formato, então a conferência, o `monta_corpo` e a mensagem do WhatsApp
    servem aos dois sem saber de onde a nota veio.
    """
    # As entidades saem ANTES do regex. A resposta crua vem com `C&oacute;digo`
    # e `N&uacute;mero`, e o navegador ja entregava resolvido -- por isso a
    # primeira versao lia codigo, numero e emissao do arquivo salvo e devolvia
    # nulo contra a SEFAZ de verdade. Sem o codigo fiscal nao ha o que mapear.
    fragmento = html.unescape(fragmento)

    itens = []
    for achado in _ITEM.finditer(fragmento):
        quantidade = _numero(achado.group("qtd"))
        unitario = _numero(achado.group("unitario"))
        total = _numero(achado.group("total"))
        descricao = _texto(achado.group("descricao"))
        if quantidade is None or unitario is None or total is None or not descricao:
            continue

        codigo = achado.group("codigo")
        itens.append({
            "ordem": len(itens) + 1,
            "descricao_fiscal": descricao,
            "codigo_fiscal": _texto(codigo) if codigo else None,
            "gtin": None,
            "quantidade_fiscal": quantidade,
            "unidade_fiscal": (_texto(achado.group("unidade")) or "UN").upper(),
            "valor_unitario": unitario,
            "valor_total": total,
        })

    chave = _CHAVE.search(fragmento)
    emitente = _EMITENTE.search(fragmento)
    cnpj = _CNPJ.search(fragmento)
    numero = _NUMERO.search(fragmento)
    serie = _SERIE.search(fragmento)
    emissao = _EMISSAO.search(fragmento)
    total = _TOTAL.search(fragmento)
    qtd_itens = _QTD_ITENS.search(fragmento)
    desconto = _DESCONTO.search(fragmento)

    emitida_em = None
    if emissao:
        d, m, a, hh, mm, ss = emissao.groups()
        emitida_em = f"{a}-{m}-{d}T{hh}:{mm}:{ss}-03:00"

    return {
        "chave_nfe": re.sub(r"\D", "", chave.group(1)) if chave else None,
        "razao_social": _texto(emitente.group(1)) if emitente else None,
        "cnpj": re.sub(r"\D", "", cnpj.group(1)) if cnpj else None,
        "numero_nota": numero.group(1) if numero else None,
        "serie": serie.group(1) if serie else None,
        "emitida_em": emitida_em,
        "valor_total": _numero(total.group(1)) if total else None,
        "valor_desconto": (_numero(desconto.group(1)) if desconto else None) or Decimal("0"),
        "itens_declarados": int(qtd_itens.group(1)) if qtd_itens else None,
        "itens": itens,
    }


def confere(lido: dict) -> dict:
    """A mesma aritmética do `le_nota`, com o que só a SEFAZ permite conferir.

    Além de a soma fechar com o total, aqui dá para comparar a quantidade de
    itens lidos com a que a nota declara — se o parser perdeu uma linha, esse
    número denuncia antes de qualquer coisa entrar no estoque.
    """
    problemas: list[str] = []
    avisos: list[str] = []
    motivo = None

    def impede(codigo: str, texto: str) -> None:
        nonlocal motivo
        if motivo is None:
            motivo = codigo
        problemas.append(texto)

    itens = lido["itens"]
    soma = sum((i["valor_total"] for i in itens), Decimal("0"))

    # Item a item: a multiplicação tem que fechar, com um centavo de folga para
    # o arredondamento que o emissor já fez. Peso fracionado (0,481 kg) cai
    # aqui igual a unidade inteira.
    fora = [
        i for i in itens
        if abs(_centavos(
            (i["quantidade_fiscal"] * i["valor_unitario"]).quantize(Decimal("0.01"))
        ) - _centavos(i["valor_total"])) > 1
    ]

    if not itens:
        impede("sem_itens", "a SEFAZ respondeu sem nenhum item reconhecível")
    if not lido["razao_social"]:
        impede("sem_emitente", "não identifiquei o emitente da nota")
    if lido["valor_total"] is None:
        impede("sem_total", "não achei o valor total na resposta da SEFAZ")
    elif itens and abs(_centavos(soma) - _centavos(
            lido["valor_total"] + lido["valor_desconto"])) > len(itens):
        impede("soma_nao_fecha",
               "a soma dos itens (R$ %s) não bate com o total da nota (R$ %s)"
               % (soma, lido["valor_total"]))

    declarados = lido.get("itens_declarados")
    if declarados is not None and itens and declarados != len(itens):
        impede("itens_faltando",
               "a nota declara %d itens e eu li %d" % (declarados, len(itens)))

    if fora:
        impede("item_nao_fecha",
               "%d item(ns) com quantidade x unitário diferente do total"
               % len(fora))

    if not lido["chave_nfe"]:
        avisos.append("sem_chave")

    return {"conferido": not problemas, "motivo": motivo,
            "problemas": problemas, "avisos": avisos, "soma_itens": soma}


def le_nota(conteudo_qr: str) -> dict:
    """QR -> SEFAZ -> nota conferida, no formato que o fluxo já consome."""
    lido = parse_fragmento(consulta(conteudo_qr))
    resultado = dict(lido)
    resultado.pop("itens_declarados", None)
    resultado.update(confere(lido))
    resultado["url_consulta"] = conteudo_qr
    resultado["total_itens"] = len(lido["itens"])
    resultado["linhas_descartadas"] = 0
    return resultado
