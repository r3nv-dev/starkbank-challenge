from app.people import random_cpf, random_person


def cpf_digits(cpf: str) -> list[int]:
    return [int(c) for c in cpf if c.isdigit()]


def is_valid_cpf(cpf: str) -> bool:
    digits = cpf_digits(cpf)
    if len(digits) != 11:
        return False
    for position in (9, 10):
        weights = range(position + 1, 1, -1)
        remainder = sum(d * w for d, w in zip(digits[:position], weights)) % 11
        expected = 0 if remainder < 2 else 11 - remainder
        if digits[position] != expected:
            return False
    return True


def test_random_cpf_has_valid_check_digits():
    for _ in range(200):
        assert is_valid_cpf(random_cpf())


def test_random_cpf_is_formatted():
    cpf = random_cpf()
    assert len(cpf) == 14
    assert cpf[3] == cpf[7] == "." and cpf[11] == "-"


def test_random_person_has_name_and_tax_id():
    person = random_person()
    assert len(person.name.split()) == 2
    assert is_valid_cpf(person.tax_id)
