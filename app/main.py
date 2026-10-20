"""Punto de entrada de la aplicación de procesamiento de PDF.

La conexión con el correo se implementará cuando se defina el proveedor.
"""

import argparse


def check_setup() -> int:
    """Comprueba que el punto de entrada está disponible."""
    print("Procesador de PDF: estructura inicial disponible.")
    print("Estado: la conexión con el correo todavía no está configurada.")
    print("Siguiente paso: definir el proveedor de correo y el destino de Excel.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Procesa PDF recibidos por correo y organiza sus datos en Excel."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Comprueba que la aplicación puede iniciarse.",
    )
    args = parser.parse_args()

    if args.check:
        return check_setup()

    parser.error(
        "La aplicación aún no está configurada. Ejecuta con --check para verificar "
        "la estructura inicial."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
