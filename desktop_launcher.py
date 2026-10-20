"""Entrada portable de Windows: ventana sin consola, Python incluido en el EXE."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from depurador.escritorio import _prueba_local, main


def verificar_ejecutable(destino: str) -> int:
    """Prueba el EXE ya empaquetado (usada solo por el compilador de GitHub)."""
    try:
        resumen, _ = _prueba_local()
        correcto = (
            resumen["encontrados"] == 1
            and resumen["agregados"] == 1
            and resumen["duplicados"] == 0
            and resumen["errores"] == 0
        )
        resultado = {"correcto": correcto, "resumen": resumen}
    except Exception as error:
        resultado = {"correcto": False, "tipo_error": type(error).__name__}
    Path(destino).write_text(json.dumps(resultado, ensure_ascii=False), encoding="utf-8")
    return 0 if resultado["correcto"] else 1


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--portable-self-test":
        sys.exit(verificar_ejecutable(sys.argv[2]))
    main()
