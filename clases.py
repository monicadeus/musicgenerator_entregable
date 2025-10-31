class Cancion:
    def __init__(self, nombre, formato, ruta_archivo):
        self.nombre = nombre
        self.formato = formato
        self.ruta_archivo = ruta_archivo
        self.pistas = []

    def cargar_metadatos(self):
        pass

    def agregar_pista(self, pistas):
        self.pistas.append(pistas)

    def separar_pistas(self):
        #llama a la API y lo hace
        pass

    def __str__(self):
        description = f"Nombre: {self.nombre} \n"
        description += f"Formato: {self.formato} \n"
        description += f"Ruta archivo: {self.ruta_archivo} \n"
        if self.pistas:
            description += "Pistas:\n"
            for p in self.pistas:
                description += f"  - {p.tipo}\n"
        return description

class Pista:
    def __init__(self, tipo, ruta_archivo):
        self.tipo = tipo
        self.ruta_archivo = ruta_archivo

    def __str__(self):
        description = f"Tipo: {self.tipo} \n"
        description += f"Ruta archivo: {self.ruta_archivo} \n"
        return description

class ProyectoAudio:
    def __init__(self, nombre_proyecto):
        self.nombre_proyecto = nombre_proyecto
        self.canciones = []

    def guardar_cancion(self, cancion):
        self.canciones.append(cancion)

    def __str__(self):
        description = f"Nombre: {self.nombre_proyecto} \n"
        description += f"--- CANCIONES --- \n"
        for cancion in self.canciones:
            description += f" - {cancion} \n"