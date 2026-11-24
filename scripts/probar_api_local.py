from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.soporte_api import ApiDePrueba


def main():
    archivo = Path(__file__).resolve().parents[1] / "docs" / ".env"
    if archivo.exists():
        raise SystemExit("docs/.env ya existe; se conserva. Usa otra copia del proyecto para la prueba temporal.")
    with ApiDePrueba() as api:
        contenido = "API_ACCESS_TOKEN=" + api.token + "\n"
        with archivo.open("x", encoding="utf-8") as salida:
            salida.write(contenido)
        try:
            print("URL:", api.url, flush=True)
            print("Bearer temporal configurado en docs/.env, ignorado por Git.")
            input("Presiona Enter para cerrar la API temporal...")
        finally:
            if archivo.exists() and archivo.read_text(encoding="utf-8") == contenido:
                archivo.unlink()


if __name__ == "__main__":
    main()
