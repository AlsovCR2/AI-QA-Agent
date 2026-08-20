from app import config, sumar


def test_config_return_value():
    assert config()["clave"] == "valor"


def test_sumar_suma_correctamente():
    assert sumar(2, 2) == 4


def test_falla_intencionadamente():
    assert sumar(2, 2) == 5