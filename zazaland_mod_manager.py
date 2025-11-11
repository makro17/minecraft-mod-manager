import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import json
import webbrowser
import tempfile
import zipfile
import sys

# Intentamos importar requests para descargar desde Google Drive de forma robusta.
try:
    import requests
except Exception:
    requests = None

# --- Configuración y persistencia ---

def get_config_dir():
    """Obtiene el directorio de configuración en AppData."""
    appdata = os.getenv('APPDATA') or os.path.expanduser('~')
    config_dir = os.path.join(appdata, "MinecraftModManager")

    # Crear directorio si no existe
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    return config_dir


def get_config_path():
    """Obtiene la ruta completa del archivo de configuración."""
    return os.path.join(get_config_dir(), "config.json")


def cargar_configuracion():
    """Carga la configuración desde el archivo JSON."""
    config_default = {
        "curseforge_client_origen": r"C:\Users\marco\curseforge\minecraft\Instances\zazaland client",
        "curseforge_client_destino": r"C:\Juegos\Minecraft\Instalaciones\Zazaland",
        "curseforge_server_origen": r"C:\Users\marco\curseforge\minecraft\Instances\zazaland",
        "curseforge_server_destino": r"C:\Mis servers minecraft\Zazaland"
    }

    config_path = get_config_path()

    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Asegurarse de que todas las claves existan
                for key, value in config_default.items():
                    if key not in config:
                        config[key] = value
                return config
    except Exception as e:
        print(f"Error cargando configuración: {e}")

    return config_default


def guardar_configuracion(config):
    """Guarda la configuración en el archivo JSON."""
    try:
        config_path = get_config_path()
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo guardar la configuración:\n{e}")


# --- Utilidades de interfaz ---

def centrar_ventana(ventana, ancho=None, alto=None):
    """Centra la ventana en la pantalla."""
    if ancho is None:
        ancho = ventana.winfo_reqwidth()
    if alto is None:
        alto = ventana.winfo_reqheight()

    x = (ventana.winfo_screenwidth() // 2) - (ancho // 2)
    y = (ventana.winfo_screenheight() // 2) - (alto // 2)

    ventana.geometry(f'{ancho}x{alto}+{x}+{y}')


def crear_ventana_centrada(parent, titulo, ancho, alto):
    """Crea una ventana ya centrada para evitar parpadeo visual."""
    ventana = tk.Toplevel(parent)
    ventana.title(titulo)
    ventana.geometry(f"{ancho}x{alto}")
    ventana.resizable(False, False)

    # Centrar inmediatamente después de crear
    centrar_ventana(ventana, ancho, alto)

    # Hacerla modal
    ventana.transient(parent)
    ventana.grab_set()

    # Esperar a que se muestre
    ventana.update_idletasks()

    return ventana


def seleccionar_ruta_ventana(titulo, ruta_predeterminada, actualizar_config=None, config_key=None):
    """Abre una ventana con campo de texto y botón para elegir carpeta."""
    ventana = crear_ventana_centrada(root, titulo, 500, 160)

    # Variable para controlar si se canceló
    resultado = {"ruta": None, "cancelado": False}

    tk.Label(ventana, text=titulo, font=("Segoe UI", 11, "bold")).pack(pady=10)
    frame = tk.Frame(ventana)
    frame.pack(pady=5)

    ruta_var = tk.StringVar(value=ruta_predeterminada)
    entry = tk.Entry(frame, textvariable=ruta_var, width=50)
    entry.pack(side="left", padx=5)

    def buscar():
        ruta = filedialog.askdirectory(title=titulo, initialdir=ruta_var.get() or None)
        if ruta:
            ruta_var.set(ruta)

    ttk.Button(frame, text="📁 Buscar...", command=buscar).pack(side="left")

    def aceptar():
        nueva_ruta = ruta_var.get()
        resultado["ruta"] = nueva_ruta

        # Actualizar configuración si se proporcionó la clave
        if actualizar_config and config_key and nueva_ruta:
            actualizar_config[config_key] = nueva_ruta
            guardar_configuracion(actualizar_config)

        ventana.destroy()

    def cancelar():
        resultado["cancelado"] = True
        ventana.destroy()

    # Frame para botones
    botones_frame = tk.Frame(ventana)
    botones_frame.pack(pady=10)

    ttk.Button(botones_frame, text="Aceptar", command=aceptar).pack(side="left", padx=5)
    ttk.Button(botones_frame, text="Cancelar", command=cancelar).pack(side="left", padx=5)

    tk.Label(
        ventana,
        text="💡 Selecciona la carpeta que CONTIENE la carpeta 'mods', no la carpeta 'mods' directamente.",
        wraplength=480,
        font=("Segoe UI", 9),
        foreground="gray"
    ).pack(padx=10)

    # Manejar cierre con la X
    ventana.protocol("WM_DELETE_WINDOW", cancelar)

    # Enfocar la ventana
    ventana.focus_set()

    ventana.wait_window()

    # Retornar None si se canceló
    if resultado["cancelado"]:
        return None
    return resultado["ruta"]


# --- Nueva ventana de selección específica para la opción Minecraft ---

def descargar_archivo_drive(file_id, destino):
    """Descarga un archivo de Google Drive manejando el token de confirmación si es necesario.
    Requiere 'requests'."""
    if requests is None:
        raise RuntimeError("La librería 'requests' no está disponible. Instala requests o descarga manualmente desde el enlace.")

    URL = "https://docs.google.com/uc?export=download"
    session = requests.Session()

    # Primera petición
    response = session.get(URL, params={'id': file_id}, stream=True)

    token = None
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            token = value
            break

    if token:
        # Repetir con token de confirmación
        response = session.get(URL, params={'id': file_id, 'confirm': token}, stream=True)

    # Guardar en chunks
    CHUNK_SIZE = 32768
    with open(destino, "wb") as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk:  # filter out keep-alive
                f.write(chunk)


def seleccionar_ruta_ventana_minecraft(titulo, ruta_predeterminada):
    """Ventana de selección para la opción Minecraft que incluye el botón 'Zazaland'."""
    ventana = crear_ventana_centrada(root, titulo, 560, 200)

    resultado = {"ruta": None, "cancelado": False}

    tk.Label(ventana, text=titulo, font=("Segoe UI", 11, "bold")).pack(pady=10)
    frame = tk.Frame(ventana)
    frame.pack(pady=5)

    ruta_var = tk.StringVar(value=ruta_predeterminada)
    entry = tk.Entry(frame, textvariable=ruta_var, width=60)
    entry.pack(side="left", padx=5)

    def buscar():
        ruta = filedialog.askdirectory(title=titulo, initialdir=ruta_var.get() or None)
        if ruta:
            ruta_var.set(ruta)

    ttk.Button(frame, text="📁 Buscar...", command=buscar).pack(side="left")

    # Botón especial Zazaland
    def boton_zazaland():
        confirmed = messagebox.askyesno("Descargar Zazaland", "Se descargará y extraerá el paquete Zazaland desde Google Drive. ¿Deseas continuar?")
        if not confirmed:
            return

        # ID del archivo compartido en Google Drive (según lo proporcionado)
        file_id = "1Oh3ZJMwVKfzyt6i_O3dixJyzHpUKcAYO"
        share_url = f"https://drive.google.com/file/d/{file_id}/view"

        # Crear carpeta temporal para la descarga y extracción
        temp_root = tempfile.mkdtemp(prefix='zazaland_')
        zip_path = os.path.join(temp_root, 'zazaland.zip')
        extract_dir = os.path.join(temp_root, 'extracted')
        os.makedirs(extract_dir, exist_ok=True)

        try:
            if requests is None:
                # Si requests no está disponible, abrimos la página y pedimos al usuario descargar manualmente
                if messagebox.askyesno("requests no instalado", "La librería 'requests' no está instalada en Python y es necesaria para descargar automáticamente.\n\n¿Quieres abrir el enlace en el navegador para descargar manualmente y luego seleccionar la carpeta? (Se abrirá el navegador)"):
                    webbrowser.open(share_url)
                return

            # Descargar
            ventana.update_idletasks()
            messagebox.showinfo("Descargando...", "Comenzando la descarga. Esto puede tardar unos minutos según tu conexión.")
            descargar_archivo_drive(file_id, zip_path)

            # Extraer
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(extract_dir)

            # Buscar la carpeta 'mods' dentro de la extracción
            mods_found = None
            for root_dir, dirs, files in os.walk(extract_dir):
                for d in dirs:
                    if d.lower() == 'mods':
                        mods_found = os.path.join(root_dir, d)
                        break
                if mods_found:
                    break

            if not mods_found:
                messagebox.showerror("Error", "No se encontró una carpeta llamada 'mods' dentro del zip extraído.")
                return

            # La ruta que debe contener 'mods' es el padre de la carpeta mods
            parent_containing_mods = os.path.dirname(mods_found)
            ruta_var.set(parent_containing_mods)

            messagebox.showinfo("Listo", f"Zazaland descargado y extraído correctamente.\nLa ruta seleccionada es:\n{parent_containing_mods}")

        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al descargar o extraer Zazaland:\n{e}")

    ttk.Button(ventana, text="⬇️ Zazaland (descargar)", command=boton_zazaland).pack(pady=6)

    def aceptar():
        nueva_ruta = ruta_var.get()
        resultado["ruta"] = nueva_ruta
        ventana.destroy()

    def cancelar():
        resultado["cancelado"] = True
        ventana.destroy()

    # Frame para botones
    botones_frame = tk.Frame(ventana)
    botones_frame.pack(pady=10)

    ttk.Button(botones_frame, text="Aceptar", command=aceptar).pack(side="left", padx=5)
    ttk.Button(botones_frame, text="Cancelar", command=cancelar).pack(side="left", padx=5)

    tk.Label(
        ventana,
        text="💡 Selecciona la carpeta que CONTIENE la carpeta 'mods', no la carpeta 'mods' directamente.",
        wraplength=520,
        font=("Segoe UI", 9),
        foreground="gray"
    ).pack(padx=10)

    # Manejar cierre con la X
    ventana.protocol("WM_DELETE_WINDOW", cancelar)

    ventana.focus_set()
    ventana.wait_window()

    if resultado["cancelado"]:
        return None
    return resultado["ruta"]


# --- Lógica de copia ---

def copiar_mods(origen, destino):
    """Elimina la carpeta mods en destino y copia la de origen."""
    origen_mods = os.path.join(origen, "mods")
    destino_mods = os.path.join(destino, "mods")

    if not os.path.exists(origen_mods):
        messagebox.showerror(
            "Error",
            f"No se encontró la carpeta 'mods' en:\n{origen_mods}\n\n"
            "Asegúrate de seleccionar la carpeta que CONTIENE 'mods'."
        )
        return

    # Confirmación antes de proceder
    confirmar = messagebox.askyesno(
        "Confirmar",
        f"Se eliminará la carpeta 'mods' en destino y se copiará la nueva.\n\n"
        f"Origen: {origen_mods}\n"
        f"Destino: {destino_mods}\n\n"
        f"¿Continuar?"
    )

    if not confirmar:
        return

    # Eliminar carpeta mods destino si existe
    if os.path.exists(destino_mods):
        try:
            shutil.rmtree(destino_mods)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar la carpeta mods destino:\n{e}")
            return

    try:
        shutil.copytree(origen_mods, destino_mods)
        messagebox.showinfo("Éxito", f"Carpeta 'mods' copiada correctamente a:\n{destino_mods}")
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo copiar la carpeta mods:\n{e}")


# --- Opciones principales ---

def opcion_curseforge_client():
    config = cargar_configuracion()

    origen = seleccionar_ruta_ventana(
        "Selecciona la carpeta de la instancia del CLIENT",
        config["curseforge_client_origen"],
        config,
        "curseforge_client_origen"
    )
    if origen is None:  # Si se canceló
        return

    destino = seleccionar_ruta_ventana(
        "Selecciona la carpeta destino del CLIENT",
        config["curseforge_client_destino"],
        config,
        "curseforge_client_destino"
    )
    if destino is None:  # Si se canceló
        return

    copiar_mods(origen, destino)


def opcion_curseforge_server():
    config = cargar_configuracion()

    origen = seleccionar_ruta_ventana(
        "Selecciona la carpeta de la instancia del SERVER",
        config["curseforge_server_origen"],
        config,
        "curseforge_server_origen"
    )
    if origen is None:  # Si se canceló
        return

    destino = seleccionar_ruta_ventana(
        "Selecciona la carpeta destino del SERVER",
        config["curseforge_server_destino"],
        config,
        "curseforge_server_destino"
    )
    if destino is None:  # Si se canceló
        return

    copiar_mods(origen, destino)


def opcion_minecraft():
    # Para la opción Minecraft usamos la ventana especializada con el botón Zazaland
    origen = seleccionar_ruta_ventana_minecraft(
        "Selecciona la carpeta que CONTIENE la carpeta 'mods' que deseas copiar",
        ""
    )
    if origen is None:  # Si se canceló
        return

    user = os.getenv("USERNAME") or os.path.basename(os.path.expanduser('~'))
    destino_default = fr"C:\Users\{user}\AppData\Roaming\.minecraft"

    destino = seleccionar_ruta_ventana(
        "Selecciona la carpeta destino (.minecraft)",
        destino_default
    )
    if destino is None:  # Si se canceló
        return

    copiar_mods(origen, destino)


# --- Interfaz principal ---

root = tk.Tk()
root.title("minecraft mod manager")
root.geometry("400x360")  # Aumentado para acomodar instrucciones
root.resizable(False, False)

# Centrar ventana principal inmediatamente
root.withdraw()  # Ocultar temporalmente para evitar parpadeo
root.update()
centrar_ventana(root, 400, 360)
root.deiconify()  # Mostrar ya centrada

# Contenido de la interfaz
tk.Label(root, text="minecraft mod manager", font=("Segoe UI", 14, "bold")).pack(pady=15)

ttk.Button(root, text="curseforge client", command=opcion_curseforge_client, width=30).pack(pady=6)
ttk.Button(root, text="curseforge server", command=opcion_curseforge_server, width=30).pack(pady=6)
ttk.Button(root, text="minecraft", command=opcion_minecraft, width=30).pack(pady=6)

# Botón para abrir la web
def abrir_web():
    webbrowser.open("https://makro17.github.io")

ttk.Button(root, text="🌐 Abrir Web", command=abrir_web, width=30).pack(pady=10)

# Nota sobre requests
if requests is None:
    tk.Label(root, text="(Nota: para descargar Zazaland automáticamente se recomienda instalar 'requests'.)", font=("Segoe UI", 8), foreground="gray").pack()

# Frame para el footer
footer_frame = tk.Frame(root)
footer_frame.pack(side="bottom", fill="x", pady=10)

tk.Label(footer_frame, text="© 2025 makro", font=("Segoe UI", 8)).pack()

root.mainloop()
