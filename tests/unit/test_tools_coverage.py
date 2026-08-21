"""Tests de la herramienta `analyze_coverage` (T059, FR-017/018/019).

Cubre: cobertura real global y por archivo; estado no_ejecutado ante fallo;
solo comandos autorizados.
"""

from __future__ import annotations

from unittest.mock import Mock, patch


from qa_agent.tools.ejecucion import (
    COMANDO_NO_PERMITIDO,
    RUTA_INVALIDA,
    SIN_EJECUTAR,
)
from qa_agent.tools.analyze_coverage import AnalyzeCoverageHerramienta
from qa_agent.tools.base import EstadoResultado


# Igual que en `run_tests`: un rechazo previo a la ejecución ya no devuelve un
# diccionario vacío, sino la causa legible por máquina (T209 / FR-106).
def _assert_rechazo_sin_ejecutar(resultado, causa_esperada):
    assert resultado.estado in {EstadoResultado.ERROR, EstadoResultado.INVALIDO}
    assert resultado.datos["causa_no_ejecutado"] == causa_esperada
    assert resultado.datos["exit_code"] == SIN_EJECUTAR
    # Ningún dato de cobertura: nada puede leerse como una medición real.
    assert "cobertura_global" not in resultado.datos
    assert "por_archivo" not in resultado.datos



def test_analyze_coverage_reporte_real(tmp_path):
    """T059: reporta cobertura global y por archivo reales (SC-002)."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calculadora.py").write_text(
        'def sumar(a, b): return a + b\n'
        'def dividir(a, b):\n'
        '    if b == 0: raise ValueError("Error")\n'
        '    return a / b\n'
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calc.py").write_text(
        'from src.calculadora import sumar, dividir\n'
        'def test_sumar(): assert sumar(2, 3) == 5\n'
        'def test_dividir(): assert dividir(10, 2) == 5.0\n'
    )

    # Mock subprocess para simular cobertura
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout=(
                "Name                 Stmts   Miss  Cover\n"
                "---------------------------------------\n"
                "src/calculadora.py       4      1    75%\n"
                "---------------------------------------\n"
                "TOTAL                    4      1    75%\n"
            ),
            stderr="",
            returncode=0,
        )

        herramienta = AnalyzeCoverageHerramienta([str(tmp_path)])
        resultado = herramienta.ejecutar(
            {
                "ruta": str(tmp_path),
                "comando_cobertura": "pytest --cov=src --cov-report=term",
            }
        )

    assert resultado.estado == EstadoResultado.EXITO
    assert "cobertura_global" in resultado.datos
    assert "por_archivo" in resultado.datos
    assert "estado" in resultado.datos
    assert resultado.datos["cobertura_global"] == 75.0
    assert len(resultado.datos["por_archivo"]) == 1
    assert resultado.datos["por_archivo"][0]["ruta_relativa"] == "src/calculadora.py"
    assert resultado.datos["por_archivo"][0]["cobertura"] == 75.0
    assert resultado.datos["estado"] == "exito"


def test_analyze_coverage_fallo_ejecucion_estado_explicito(tmp_path):
    """T059: fallo de ejecución → estado error/no_ejecutado explícito (SC-005)."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calculadora.py").write_text("def sumar(a, b): return a + b\n")

    with patch("subprocess.run") as mock_run:
        # Simular error de ejecución (OSError es capturado por la herramienta)
        mock_run.side_effect = OSError("Command failed")

        herramienta = AnalyzeCoverageHerramienta([str(tmp_path)])
        resultado = herramienta.ejecutar(
            {
                "ruta": str(tmp_path),
                "comando_cobertura": "pytest --cov=src --cov-report=term",
            }
        )

    assert resultado.estado == EstadoResultado.ERROR
    assert resultado.datos.get("estado") in {"error", "no_ejecutado"}


def test_analyze_coverage_comando_no_autorizado_rechazado(tmp_path):
    """T059: comando fuera de allowlist → rechazado (SC-011)."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calculadora.py").write_text("def sumar(a, b): return a + b\n")

    herramienta = AnalyzeCoverageHerramienta([str(tmp_path)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(tmp_path),
            "comando_cobertura": "rm -rf /",  # Peligroso
        }
    )

    _assert_rechazo_sin_ejecutar(resultado, COMANDO_NO_PERMITIDO)


def test_analyze_coverage_ruta_fuera_allowlist(tmp_path):
    """AnalyzeCoverage respeta Allowlist."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calculadora.py").write_text("def sumar(a, b): return a + b\n")
    outside = tmp_path.parent / "otro"
    outside.mkdir(exist_ok=True)

    herramienta = AnalyzeCoverageHerramienta([str(tmp_path)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(outside),
            "comando_cobertura": "pytest --cov=src --cov-report=term",
        }
    )

    _assert_rechazo_sin_ejecutar(resultado, RUTA_INVALIDA)


# -- Ampliación multi-lenguaje: cobertura dotnet (Cobertura XML) y maven (JaCoCo) ----

_XML_COBERTURA_DOTNET = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<coverage line-rate="0.75" branch-rate="0.5" lines-covered="3" lines-valid="4" '
    'branches-covered="0" branches-valid="0" complexity="0">\n'
    '  <sources><source>.</source></sources>\n'
    '  <packages>\n'
    '    <package name="Calculadora" line-rate="0.75" branch-rate="0.5">\n'
    '      <classes>\n'
    '        <class name="Calculadora.Calculadora" filename="Calculadora.cs" line-rate="0.75" '
    'branch-rate="0.5" complexity="1">\n'
    '          <methods><method name="Sumar" signature="()" line-rate="1" branch-rate="1">\n'
    '            <lines><line number="1" hits="1"/></lines>\n'
    '          </method></methods>\n'
    '          <lines>\n'
    '            <line number="1" hits="1"/>\n'
    '            <line number="2" hits="1"/>\n'
    '            <line number="3" hits="1"/>\n'
    '            <line number="4" hits="0"/>\n'
    '          </lines>\n'
    '        </class>\n'
    '      </classes>\n'
    '    </package>\n'
    '  </packages>\n'
    '</coverage>\n'
)

_XML_JACOCO_MAVEN = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<report name="Calculadora">\n'
    '  <package name="com/example">\n'
    '    <class name="com/example/Calculadora" sourcefilename="Calculadora.java">\n'
    '      <method name="sumar" desc="()I" line="10">\n'
    '        <counter type="LINE" missed="0" covered="3"/>\n'
    '      </method>\n'
    '      <counter type="LINE" missed="1" covered="3"/>\n'
    '      <counter type="BRANCH" missed="1" covered="1"/>\n'
    '    </class>\n'
    '  </package>\n'
    '  <counter type="LINE" missed="1" covered="3"/>\n'
    '  <counter type="BRANCH" missed="1" covered="1"/>\n'
    '</report>\n'
)


def test_analyze_coverage_dotnet_cobertura_xml(tmp_path):
    """dotnet test con collect de cobertura → parsea Cobertura XML real (SC-002)."""
    (tmp_path / "TestResults").mkdir()
    xml_file = tmp_path / "TestResults" / "coverage.cobertura.xml"
    xml_file.write_text(_XML_COBERTURA_DOTNET, encoding="utf-8")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout=(
                "  Determinar proyectos para restaurar...\n"
                "Attachments:\n"
                f"  {xml_file}\n"
            ),
            stderr="",
            returncode=0,
        )

        herramienta = AnalyzeCoverageHerramienta([str(tmp_path)])
        resultado = herramienta.ejecutar(
            {
                "ruta": str(tmp_path),
                "comando_cobertura": 'dotnet test --collect:"XPlat Code Coverage"',
            }
        )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["cobertura_global"] == 75.0
    assert resultado.datos["estado"] == "exito"
    assert len(resultado.datos["por_archivo"]) == 1
    archivo = resultado.datos["por_archivo"][0]
    assert archivo["ruta_relativa"] == "Calculadora.cs"
    assert archivo["cobertura"] == 75.0
    assert archivo["lineas_faltantes"] == [4]


def test_analyze_coverage_maven_jacoco_xml(tmp_path):
    """mvn test jacoco:report → parsea JaCoCo XML real."""
    jacoco_dir = tmp_path / "target" / "site" / "jacoco"
    jacoco_dir.mkdir(parents=True)
    xml_file = jacoco_dir / "jacoco.xml"
    xml_file.write_text(_XML_JACOCO_MAVEN, encoding="utf-8")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout=(
                "[INFO] --- jacoco-maven-plugin:0.8.11:report ---\n"
                "[INFO] Building jacoco report... file://" + str(xml_file).replace("\\", "/") + "\n"
            ),
            stderr="",
            returncode=0,
        )

        herramienta = AnalyzeCoverageHerramienta([str(tmp_path)])
        resultado = herramienta.ejecutar(
            {
                "ruta": str(tmp_path),
                "comando_cobertura": "mvn test jacoco:report",
            }
        )

    assert resultado.estado == EstadoResultado.EXITO
    # LINE: 3 covered de 4 → 75%
    assert resultado.datos["cobertura_global"] == 75.0
    assert resultado.datos["estado"] == "exito"
    assert len(resultado.datos["por_archivo"]) == 1
    archivo = resultado.datos["por_archivo"][0]
    assert archivo["ruta_relativa"] == "Calculadora.java"
    assert archivo["cobertura"] == 75.0


def test_analyze_coverage_comando_multilenguaje_fuera_allowlist_rechazado(tmp_path):
    """Variantes no permitidas de dotnet/mvn se rechazan (SC-011)."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Program.cs").write_text("class Program { static void Main() {} }\n")

    herramienta = AnalyzeCoverageHerramienta([str(tmp_path)])
    for comando in (
        'dotnet test --collect:"XPlat Code Coverage" --filter TestCategory=Unit',
        "mvn test jacoco:report -DskipTests",
    ):
        resultado = herramienta.ejecutar(
            {
                "ruta": str(tmp_path),
                "comando_cobertura": comando,
            }
        )
    _assert_rechazo_sin_ejecutar(resultado, COMANDO_NO_PERMITIDO)