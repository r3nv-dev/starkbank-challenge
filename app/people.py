"""Random (but structurally valid) people to receive invoices."""
import random
from dataclasses import dataclass

FIRST_NAMES = [
    "Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gabriela", "Henrique",
    "Isabela", "João", "Karina", "Lucas", "Mariana", "Nicolas", "Olívia", "Paulo",
]
LAST_NAMES = [
    "Almeida", "Barbosa", "Cardoso", "Duarte", "Ferreira", "Gonçalves", "Lima",
    "Martins", "Nogueira", "Oliveira", "Pereira", "Ribeiro", "Silva", "Souza",
]


@dataclass(frozen=True)
class Person:
    name: str
    tax_id: str


def _cpf_check_digit(digits: list[int]) -> int:
    weights = range(len(digits) + 1, 1, -1)
    remainder = sum(d * w for d, w in zip(digits, weights)) % 11
    return 0 if remainder < 2 else 11 - remainder


def random_cpf() -> str:
    """Generate a CPF with valid check digits."""
    digits = [random.randint(0, 9) for _ in range(9)]
    digits.append(_cpf_check_digit(digits))
    digits.append(_cpf_check_digit(digits))
    cpf = "".join(map(str, digits))
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def random_person() -> Person:
    name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    return Person(name=name, tax_id=random_cpf())
