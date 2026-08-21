"""Calculadora mínima usada como proyecto de referencia de la evaluación."""


def sumar(a: int, b: int) -> int:
    return a + b


def dividir(a: int, b: int) -> float:
    if b == 0:
        raise ValueError("division por cero")
    return a / b
