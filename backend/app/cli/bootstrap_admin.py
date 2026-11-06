import getpass
import os

from email_validator import EmailNotValidError, validate_email

from app.core.errors import AppError
from app.db.session import SessionLocal
from app.services.bootstrap import bootstrap_admin


def main() -> int:
    name = os.getenv("ADMIN_NAME") or input("Nome do administrador: ").strip()
    raw_email = os.getenv("ADMIN_EMAIL") or input("E-mail do administrador: ").strip()
    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Senha do administrador: ")

    try:
        email = validate_email(raw_email, check_deliverability=False).normalized
    except EmailNotValidError:
        print("Erro: informe um e-mail válido.")
        return 1

    with SessionLocal() as db:
        try:
            user, created = bootstrap_admin(
                db, name=name, email=email, password=password
            )
        except AppError as error:
            print(f"Erro: {error.message}")
            return 1

    status = "criado" if created else "já existente"
    print(f"Administrador {status}: {user.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
