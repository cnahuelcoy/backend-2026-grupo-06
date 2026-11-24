from pathlib import Path
import secrets


def main():
    raiz = Path(__file__).resolve().parents[1]
    archivo = raiz / ".env"
    contenido = (archivo if archivo.exists() else raiz / ".env.example").read_text(encoding="utf-8-sig")
    lineas = contenido.splitlines()
    cambio = False
    indice = next((i for i, linea in enumerate(lineas) if linea.startswith("JWT_SECRET_KEY=")), None)
    if indice is not None:
        valor = lineas[indice].split("=", 1)[1].strip().strip("\"'")
    else:
        valor = ""
    if not valor or valor.startswith("CAMBIAR_"):
        nueva = "JWT_SECRET_KEY=" + secrets.token_urlsafe(48)
        if indice is None:
            lineas.append(nueva)
        else:
            lineas[indice] = nueva
        cambio = True
    for nombre, valor_default in (("JWT_ACCESS_MINUTES", "15"), ("ADMIN_EMAIL", ""), ("ADMIN_PASSWORD", "")):
        if not any(linea.startswith(nombre + "=") for linea in lineas):
            posicion = next((i for i, linea in enumerate(lineas) if linea.startswith("ADMIN_EMAIL=")), len(lineas))
            lineas.insert(posicion if nombre == "JWT_ACCESS_MINUTES" else len(lineas), nombre + "=" + valor_default)
            cambio = True
    if cambio:
        archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("Configuración de autenticación lista en .env. Los valores existentes se conservan y no se muestran.")


if __name__ == "__main__":
    main()
