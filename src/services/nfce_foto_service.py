"""Leitura do QR code de um cupom NFC-e fotografado.

O caso comum não é o PDF: é alguém apontando o celular para o cupom em cima do
balcão. Foto tem sombra, dobra, reflexo de flash e mão tremida, então a leitura
tenta a imagem em algumas formas antes de desistir — e quando desiste, diz que
desistiu, em vez de devolver meia chave.

O QR da NFC-e carrega a URL de consulta da SEFAZ, e dentro dela a chave de 44
dígitos. A chave é o que interessa: é ela que identifica a nota, e é ela que
faz `POST /admin/inventory/compras` ser idempotente.

Quem decodifica é o `zxingcpp`; o `opencv` continua, mas só para abrir e
corrigir a imagem. A escolha foi medida, não opinada — a mesma bateria de fotos
degradadas nos dois leitores:

    zxing na escada    11/12 acertos    4,3 s no total    pior caso  1,3 s
    opencv na escada   11/12 acertos   22,8 s no total    pior caso 14,6 s

Mesmo acerto, cinco vezes mais rápido, e um pior caso que cabe numa requisição
HTTP. O `QRCodeDetector` do opencv não acertou nada que o zxingcpp errasse, e
mantê-lo como fallback custaria 2,9 s em toda foto SEM código fiscal — que é
justamente o caso mais comum, o comprovante de pagamento.

Nenhum dos dois lê um cupom torto a 20 graus. É por isso que a mensagem de
falha manda enquadrar reto.

Os dois pacotes trazem roda `manylinux` para cp312, então o `python:3.12-slim`
segue sem `apt install` nenhum — que era o ponto de não usar `pyzbar`.
"""
import base64
import binascii
import re

import cv2
import numpy as np
import zxingcpp

# A chave aparece na URL como `?p=<44 dígitos>|versão|ambiente|...` (padrão da
# NFC-e) ou como `chNFe=<44 dígitos>` (algumas UFs).
_CHAVE_NA_URL = re.compile(r"[?&](?:p|chNFe)=(\d{44})", re.IGNORECASE)
_CHAVE_SOLTA = re.compile(r"\b(\d{44})\b")

# Uma foto de cupom raramente passa de 2 MB; acima disso é outra coisa.
LIMITE_BYTES = 8 * 1024 * 1024


class ImagemInvalida(ValueError):
    pass


def decodifica_base64(dados: str) -> np.ndarray:
    """Base64 (com ou sem prefixo data:) para matriz de pixels."""
    if not dados:
        raise ImagemInvalida("imagem vazia")

    if dados.startswith("data:"):
        _, _, dados = dados.partition(",")

    try:
        crus = base64.b64decode(dados, validate=False)
    except (binascii.Error, ValueError) as erro:
        raise ImagemInvalida("base64 inválido") from erro

    if not crus:
        raise ImagemInvalida("imagem vazia")
    if len(crus) > LIMITE_BYTES:
        raise ImagemInvalida("imagem acima de 8 MB")

    imagem = cv2.imdecode(np.frombuffer(crus, np.uint8), cv2.IMREAD_COLOR)
    if imagem is None:
        raise ImagemInvalida("não consegui abrir a imagem")
    return imagem


def _variantes(imagem: np.ndarray):
    """A mesma foto em algumas formas, da mais barata para a mais cara.

    Cada uma existe por um defeito real de foto de cupom:
      original    — a foto boa, que resolve na primeira
      cinza       — tira ruído de cor de papel amarelado
      ampliada    — QR pequeno no canto do enquadramento
      contraste   — CLAHE, para sombra atravessando o código
      binarizada  — Otsu, para reflexo de flash lavando o preto
    """
    yield imagem

    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    yield cinza

    altura, largura = cinza.shape[:2]
    if max(altura, largura) < 1600:
        yield cv2.resize(cinza, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

    yield cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(cinza)

    _, binaria = cv2.threshold(cinza, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield binaria


def le_qr(imagem: np.ndarray) -> str | None:
    """Conteúdo do primeiro QR legível, ou None.

    Um cupom pode ter mais de um código — o da NFC-e e o de alguma promoção —,
    então quando vem mais de um a escolha é pelo que tem chave de 44 dígitos,
    não pelo primeiro que aparecer.
    """
    for variante in _variantes(imagem):
        if variante.ndim == 2:
            rgb = cv2.cvtColor(variante, cv2.COLOR_GRAY2RGB)
        else:
            rgb = cv2.cvtColor(variante, cv2.COLOR_BGR2RGB)

        try:
            achados = [r.text for r in zxingcpp.read_barcodes(rgb) if r.text]
        except Exception:
            achados = []

        if achados:
            return _escolhe_nfce(achados) or achados[0]

    return None


def _escolhe_nfce(textos) -> str | None:
    """Entre vários QR na mesma foto, o que tem chave de 44 dígitos."""
    for texto in textos:
        if texto and extrai_chave(texto):
            return texto
    return None


def extrai_chave(conteudo: str | None) -> str | None:
    """A chave de 44 dígitos dentro do conteúdo do QR."""
    if not conteudo:
        return None

    achado = _CHAVE_NA_URL.search(conteudo)
    if achado:
        return achado.group(1)

    achado = _CHAVE_SOLTA.search(conteudo)
    if achado:
        return achado.group(1)

    # Sem separador reconhecível: sobra tentar o primeiro campo, que é onde o
    # padrão da NFC-e coloca a chave.
    primeiro = conteudo.split("|")[0].strip()
    somente_digitos = re.sub(r"\D", "", primeiro)
    if len(somente_digitos) == 44:
        return somente_digitos

    return None


def url_de_consulta(conteudo: str | None) -> str | None:
    """A URL da SEFAZ que estava no QR, quando o conteúdo é uma URL."""
    if not conteudo:
        return None
    conteudo = conteudo.strip()
    return conteudo if conteudo.lower().startswith(("http://", "https://")) else None


def detecta(imagem_base64: str) -> dict:
    """O que dá para saber da foto sem falar com a SEFAZ.

    É o que a classificação de anexo do `julia_entrada` consome: barata,
    determinística e sem chamada externa.
    """
    imagem = decodifica_base64(imagem_base64)
    conteudo = le_qr(imagem)
    chave = extrai_chave(conteudo)

    return {
        "tem_qr": conteudo is not None,
        "e_nfce": chave is not None,
        "chave_nfe": chave,
        "url_consulta": url_de_consulta(conteudo),
        "conteudo_qr": conteudo,
    }
