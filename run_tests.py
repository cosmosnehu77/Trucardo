#!/usr/bin/env python3
"""Corre los tests sin pytest:

    python3 run_tests.py

Con pytest instalado, `pytest` corre los mismos.
"""

import importlib
import pkgutil
import sys
import traceback

import tests


def main() -> int:
    pasaron, fallaron = 0, []

    for info in sorted(pkgutil.iter_modules(tests.__path__), key=lambda m: m.name):
        if not info.name.startswith("test_"):
            continue
        modulo = importlib.import_module(f"tests.{info.name}")
        print(f"\n{info.name}")
        for nombre in sorted(vars(modulo)):
            if not nombre.startswith("test_"):
                continue
            funcion = getattr(modulo, nombre)
            if not callable(funcion):
                continue
            try:
                funcion()
            except Exception:
                fallaron.append(f"{info.name}.{nombre}")
                print(f"  FALLO  {nombre}")
                print("".join(f"         {l}" for l in traceback.format_exc().splitlines(True)))
            else:
                pasaron += 1
                print(f"  ok     {nombre}")

    print(f"\n{'-' * 50}")
    if fallaron:
        print(f"{pasaron} pasaron, {len(fallaron)} FALLARON:")
        for nombre in fallaron:
            print(f"  - {nombre}")
        return 1
    print(f"{pasaron} tests, todo ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
