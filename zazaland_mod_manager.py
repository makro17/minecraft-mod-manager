import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# --- Utilidades de interfaz ---

def seleccionar_ruta_ventana(titulo, ruta_predeterminada):
    """Abre una ventana con campo de texto y botón para elegir carpeta."""
    ventana = tk.Toplevel()
    ventana.title(titulo)
    ventana.geometry("500x160")
    ventana.resizable(False, False)
    ventana.grab_set()
    
    # Variable para controlar si se canceló
    resultado = {"ruta": None, "cancelado": False}

    tk.Label(ventana, text=titulo, font=("Segoe UI", 11, "bold")).pack(pady=10)
    frame = tk.Frame(ventana)
    frame.pack(pady=5)

    ruta_var = tk.StringVar(value=ruta_predeterminada)
    entry = tk.Entry(frame, textvariable=ruta_var, width=50)
    entry.pack(side="left", padx=5)

    def buscar():
        ruta = filedialog.askdirectory(title=titulo, initialdir=ruta_var.get())
        if ruta:
            ruta_var.set(ruta)

    ttk.Button(frame, text="📁 Buscar...", command=buscar).pack(side="left")

    def aceptar():
        resultado["ruta"] = ruta_var.get()
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

    ventana.wait_window()
    
    # Retornar None si se canceló
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
    origen_default = r"C:\Users\marco\curseforge\minecraft\Instances\zazaland client"
    destino_default = r"C:\Juegos\Minecraft\Instalaciones\Zazaland"

    origen = seleccionar_ruta_ventana("Selecciona la carpeta de la instancia del CLIENT", origen_default)
    if origen is None:  # Si se canceló
        return
    
    destino = seleccionar_ruta_ventana("Selecciona la carpeta destino del CLIENT", destino_default)
    if destino is None:  # Si se canceló
        return
        
    copiar_mods(origen, destino)

def opcion_curseforge_server():
    origen_default = r"C:\Users\marco\curseforge\minecraft\Instances\zazaland"
    destino_default = r"C:\Mis servers minecraft\Zazaland"

    origen = seleccionar_ruta_ventana("Selecciona la carpeta de la instancia del SERVER", origen_default)
    if origen is None:  # Si se canceló
        return
    
    destino = seleccionar_ruta_ventana("Selecciona la carpeta destino del SERVER", destino_default)
    if destino is None:  # Si se canceló
        return
        
    copiar_mods(origen, destino)

def opcion_minecraft():
    origen = seleccionar_ruta_ventana("Selecciona la carpeta que CONTIENE la carpeta 'mods' que deseas copiar", "")
    if origen is None:  # Si se canceló
        return

    user = os.getenv("USERNAME")
    destino_default = fr"C:\Users\{user}\AppData\Roaming\.minecraft"
    destino = seleccionar_ruta_ventana("Selecciona la carpeta destino (.minecraft)", destino_default)
    if destino is None:  # Si se canceló
        return
        
    copiar_mods(origen, destino)


# --- Interfaz principal ---

root = tk.Tk()
root.title("minecraft mod manager")
root.geometry("400x280")
root.resizable(False, False)

tk.Label(root, text="minecraft mod manager", font=("Segoe UI", 14, "bold")).pack(pady=15)

ttk.Button(root, text="curseforge client", command=opcion_curseforge_client, width=30).pack(pady=6)
ttk.Button(root, text="curseforge server", command=opcion_curseforge_server, width=30).pack(pady=6)
ttk.Button(root, text="minecraft", command=opcion_minecraft, width=30).pack(pady=6)

tk.Label(root, text="© 2025 makro", font=("Segoe UI", 8)).pack(side="bottom", pady=10)

root.mainloop()