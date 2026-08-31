from sqlalchemy.dialects.postgresql import ENUM


SCHEMA = "giardini_estoque"


def _enum(name: str, *values: str) -> ENUM:
    """Aponta para o tipo que já existe no banco.

    create_type=False é o que importa: a migração cria os tipos, o SQLAlchemy só
    os referencia. Sem isso ele tentaria criar de novo e quebraria.
    """
    return ENUM(*values, name=name, schema=SCHEMA, create_type=False)


unidade_base = _enum("unidade_base", "UN", "G", "ML")
status_mapeamento = _enum("status_mapeamento", "confirmado", "sugerido", "rejeitado")
origem_mapeamento = _enum("origem_mapeamento", "humano", "ia", "importacao")
status_compra = _enum("status_compra", "rascunho", "revisao", "aprovada", "lancada", "cancelada")
status_item_compra = _enum("status_item_compra", "mapeado", "precisa_mapeamento", "ignorado")
tipo_movimento = _enum("tipo_movimento", "compra", "consumo", "perda", "ajuste_contagem")
tipo_documento = _enum("tipo_documento", "nfce", "comprovante", "outro")
status_documento = _enum("status_documento", "recebido", "processado", "erro", "ignorado")
status_contagem = _enum("status_contagem", "aberta", "fechada", "cancelada")
