import re

import phonenumbers

from app.core.errors import AppError

ALLOWED_TEMPLATE_VARIABLES = frozenset({"nome", "produto", "loja"})
VARIABLE_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


def normalize_phone(value: str) -> str:
    try:
        parsed = phonenumbers.parse(value.strip(), "BR")
    except phonenumbers.NumberParseException:
        raise AppError(422, "invalid_phone", "Informe um telefone válido.")
    if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(parsed):
        raise AppError(422, "invalid_phone", "Informe um telefone válido.")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def validate_template_content(content: str) -> str:
    clean_content = content.strip()
    variables = set(VARIABLE_PATTERN.findall(clean_content))
    unknown = variables - ALLOWED_TEMPLATE_VARIABLES
    recognized_removed = VARIABLE_PATTERN.sub("", clean_content)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise AppError(422, "unknown_template_variable", f"Variáveis não permitidas: {names}.")
    if "{{" in recognized_removed or "}}" in recognized_removed:
        raise AppError(422, "invalid_template_syntax", "Existe uma variável com sintaxe inválida.")
    return clean_content


def render_template(content: str, *, name: str, product: str, store: str) -> str:
    values = {"nome": name, "produto": product, "loja": store}

    def replace(match: re.Match[str]) -> str:
        return values[match.group(1)]

    return VARIABLE_PATTERN.sub(replace, content)
