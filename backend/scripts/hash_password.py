"""Gera hash bcrypt para colocar em VENDEDOR_PASSWORD_HASH / PROPRIETARIA_PASSWORD_HASH."""

import getpass
import sys

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "senha"
    p = getpass.getpass(f"{label}: ")
    print(pwd_context.hash(p))


if __name__ == "__main__":
    main()
