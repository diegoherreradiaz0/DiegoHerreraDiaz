import sys
import json

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QLabel,
    QMessageBox, QAbstractItemView, QHeaderView, QGroupBox
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

# =====================================================================
# CONFIGURACIÓN DE LAS TABLAS - Sistema de Recursos Materiales ITJ
# En ambos motores los nombres de tablas y columnas son snake_case,
# por eso (nombre, nombre) se repite. Cada campo se declara como:
#   (columna, etiqueta, obligatorio, tipo)
# Si el nombre de alguna columna difiere en tu BD, cámbialo aquí.
# =====================================================================
def _t(tabla, pk, campos, grupo, buscar=0):
    return {
        "tabla": (tabla, tabla),
        "pk": (pk, pk),
        "pk_tipo": "int",
        # (clave_interna, etiqueta, (col_pg, col_ss), obligatorio, tipo)
        "campos": [(c, e, (c, c), o, t) for c, e, o, t in campos],
        "grupo": grupo,    # a qué menú pertenece
        "buscar": buscar,  # índice del campo usado en el buscador
    }


CATALOGOS = {
    # ---- Menú "Catálogos" (tablas maestras) ----
    "Categorías": _t("categoria", "id_categoria", [
        ("nombre_categoria", "Nombre", True, "str"),
        ("descripcion", "Descripción", False, "str"),
    ], "Catálogos"),
    "Roles": _t("rol", "id_rol", [
        ("nombre_rol", "Nombre del rol", True, "str"),
        ("descripcion", "Descripción", False, "str"),
    ], "Catálogos"),
    "Usuarios": _t("usuario", "id_usuario", [
        ("nombre", "Nombre(s)", True, "str"),
        ("apellidos", "Apellidos", True, "str"),
        ("correo_institucional", "Correo institucional", True, "str"),
        ("password", "Contraseña / hash", True, "str"),
        ("id_rol", "ID Rol", True, "int"),
    ], "Catálogos"),
    "Artículos": _t("articulo", "id_articulo", [
        ("codigo_inventario", "Código inventario", True, "str"),
        ("nombre_articulo", "Nombre del artículo", True, "str"),
        ("descripcion", "Descripción", False, "str"),
        ("stock_disponible", "Stock disponible", True, "int"),
        ("stock_minimo", "Stock mínimo", True, "int"),
        ("id_categoria", "ID Categoría", True, "int"),
    ], "Catálogos", buscar=1),

    # ---- Menú "Movimientos" (tablas de operación) ----
    "Entradas de material": _t("entrada_material", "id_entrada", [
        ("fecha_ingreso", "Fecha ingreso (AAAA-MM-DD HH:MM:SS)", True, "str"),
        ("proveedor", "Proveedor", True, "str"),
        ("cantidad_recibida", "Cantidad recibida", True, "int"),
        ("id_articulo", "ID Artículo", True, "int"),
        ("id_usuario", "ID Usuario receptor", True, "int"),
    ], "Movimientos", buscar=1),
    "Solicitudes de préstamo": _t("solicitud_prestamo", "id_solicitud", [
        ("fecha_solicitud", "Fecha solicitud (AAAA-MM-DD HH:MM:SS)", True, "str"),
        ("fecha_limite_devolucion", "Fecha límite (AAAA-MM-DD)", True, "str"),
        ("estatus", "Estatus (Pendiente/Aprobado/...)", True, "str"),
        ("id_usuario", "ID Usuario solicitante", True, "int"),
    ], "Movimientos", buscar=2),
    "Detalle de préstamo": _t("detalle_prestamo", "id_detalle", [
        ("id_solicitud", "ID Solicitud", True, "int"),
        ("id_articulo", "ID Artículo", True, "int"),
        ("cantidad_solicitada", "Cantidad solicitada", True, "int"),
    ], "Movimientos"),
    "Devoluciones": _t("devolucion", "id_devolucion", [
        ("fecha_real_devolucion", "Fecha devolución (AAAA-MM-DD HH:MM:SS)", True, "str"),
        ("estado_fisico", "Estado físico", True, "str"),
        ("observaciones", "Observaciones", False, "str"),
        ("id_solicitud", "ID Solicitud", True, "int"),
    ], "Movimientos", buscar=1),
}


# =====================================================================
# CAPA DE BASE DE DATOS
# Envuelve TUS clases de conexión. Aquí se decide el motor y el
# marcador de parámetros: psycopg2 usa %s y mssql_python usa ?
# =====================================================================
class Gestor:
    def __init__(self, motor):
        self.motor = motor                       # "pg" o "ss"
        self.idx = 0 if motor == "pg" else 1     # posición del nombre en las tuplas
        self.ph = "%s" if motor == "pg" else "?"  # marcador de parámetro
        # Se importa aquí para que, si falta una librería, solo falle ese motor
        if motor == "pg":
            from conexion_posgress import ConexionPostgres
            self.cnn = ConexionPostgres()
        else:
            from conexion_sqlserver import ConecionSqlServer
            self.cnn = ConecionSqlServer()

    def conectar(self):
        # crear_conexion() devuelve None si falla
        return self.cnn.crear_conexion() is not None

    def ejecutar(self, sql, params=None):
        # ejecutar_consulta() devuelve un JSON (texto); lo convertimos a dict
        return json.loads(self.cnn.ejecutar_consulta(sql, params))

    def nom(self, par):
        # Elige el nombre de tabla/columna según el motor activo
        return par[self.idx]

    def cerrar(self):
        self.cnn.cerrar_conexion()


# =====================================================================
# WIDGET GENÉRICO DE CRUD (sirve para cualquier tabla del diccionario)
# =====================================================================
class CatalogoWidget(QWidget):
    def __init__(self, titulo, cfg, gestor):
        super().__init__()
        self.cfg = cfg
        self.g = gestor
        self.campos = cfg["campos"]
        self.claves = ["id"] + [c[0] for c in self.campos]

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<h2>Catálogo de {titulo}</h2>"))

        # ---- Formulario ----
        caja = QGroupBox("Datos del registro")
        form = QFormLayout(caja)
        self.txt_id = QLineEdit()
        if cfg["pk_tipo"] == "int":
            self.txt_id.setReadOnly(True)
            self.txt_id.setPlaceholderText("(se asigna automáticamente)")
        else:
            self.txt_id.setPlaceholderText("Escribe el ID (ej. ALFKI)")
        form.addRow("ID:", self.txt_id)

        self.entradas = {}
        for clave, etiqueta, _, oblig, _t in self.campos:
            campo = QLineEdit()
            self.entradas[clave] = campo
            form.addRow(etiqueta + (" *" if oblig else "") + ":", campo)
        layout.addWidget(caja)

        # ---- Botones del CRUD ----
        fila_btn = QHBoxLayout()
        for texto, funcion in [
            ("Insertar", self.insertar),
            ("Actualizar", self.actualizar),
            ("Eliminar", self.eliminar),
            ("Consultar", self.consultar),
            ("Limpiar", self.limpiar),
        ]:
            b = QPushButton(texto)
            b.clicked.connect(funcion)
            fila_btn.addWidget(b)
        layout.addLayout(fila_btn)

        # ---- Búsqueda ----
        fila_busq = QHBoxLayout()
        fila_busq.addWidget(QLabel(f"Buscar por {self.campos[self.cfg['buscar']][1].lower()}:"))
        self.txt_buscar = QLineEdit()
        self.txt_buscar.returnPressed.connect(self.consultar)
        fila_busq.addWidget(self.txt_buscar)
        layout.addLayout(fila_busq)

        # ---- Tabla ----
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(len(self.claves))
        self.tabla.setHorizontalHeaderLabels(["ID"] + [c[1] for c in self.campos])
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.itemSelectionChanged.connect(self.cargar_fila)
        layout.addWidget(self.tabla)

        self.consultar()

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _error(self, r):
        detalle = r.get("error", "")
        QMessageBox.critical(self, "Error", f"{r.get('mensaje', 'Error')}\n\n{detalle}")

    def _valores(self):
        """Lee el formulario. Texto vacío -> None (NULL); enteros se validan."""
        vals = []
        for clave, etiqueta, _, oblig, tipo in self.campos:
            txt = self.entradas[clave].text().strip()
            if oblig and not txt:
                QMessageBox.warning(self, "Dato faltante", f"El campo '{etiqueta}' es obligatorio.")
                return None
            if not txt:
                vals.append(None)
            elif tipo == "int":
                try:
                    vals.append(int(txt))
                except ValueError:
                    QMessageBox.warning(self, "Dato inválido", f"'{etiqueta}' debe ser un número entero.")
                    return None
            else:
                vals.append(txt)
        return vals

    def _id_valor(self):
        txt = self.txt_id.text().strip()
        if not txt:
            return None
        if self.cfg["pk_tipo"] == "int":
            try:
                return int(txt)
            except ValueError:
                return None
        return txt

    def _resultado(self, r, mensaje_ok):
        """Procesa la respuesta de INSERT/UPDATE/DELETE."""
        if not r["estado"]:
            self._error(r)
            return
        if r.get("filas_afectadas", 1) == 0:
            QMessageBox.warning(self, "Sin cambios", "No se encontró ningún registro con ese ID.")
            return
        QMessageBox.information(self, "Listo", mensaje_ok)
        self.limpiar()
        self.consultar()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def consultar(self):
        t = self.g.nom(self.cfg["tabla"])
        pk = self.g.nom(self.cfg["pk"])

        # SELECT id AS id, col1 AS clave1, ...  (los alias unifican las claves
        # del JSON entre PostgreSQL y SQL Server)
        columnas = [f"{pk} AS id"] + [f"{self.g.nom(c[2])} AS {c[0]}" for c in self.campos]
        sql = f"SELECT {', '.join(columnas)} FROM {t}"
        params = None

        filtro = self.txt_buscar.text().strip()
        if filtro:
            # El valor viaja como parámetro (nunca concatenado) -> evita inyección SQL
            col_busq = self.g.nom(self.campos[self.cfg['buscar']][2])
            sql += f" WHERE LOWER(CAST({col_busq} AS VARCHAR(200))) LIKE LOWER({self.g.ph})"
            params = (f"%{filtro}%",)
        sql += f" ORDER BY {pk}"

        r = self.g.ejecutar(sql, params)
        if not r["estado"]:
            self._error(r)
            return

        registros = r["registros"]
        self.tabla.blockSignals(True)
        self.tabla.setRowCount(len(registros))
        for i, reg in enumerate(registros):
            for j, clave in enumerate(self.claves):
                valor = reg.get(clave)
                self.tabla.setItem(i, j, QTableWidgetItem("" if valor is None else str(valor)))
        self.tabla.blockSignals(False)

    def insertar(self):
        vals = self._valores()
        if vals is None:
            return
        t = self.g.nom(self.cfg["tabla"])
        pk = self.g.nom(self.cfg["pk"])
        cols = [self.g.nom(c[2]) for c in self.campos]

        if self.cfg["pk_tipo"] == "str":
            # Clave de texto: la escribe el usuario
            id_nuevo = self.txt_id.text().strip()
            if not id_nuevo:
                QMessageBox.warning(self, "Dato faltante", "El ID es obligatorio.")
                return
            cols.insert(0, pk)
            vals.insert(0, id_nuevo)
        elif self.g.motor == "pg":
            # En PostgreSQL calculamos el siguiente ID (MAX + 1), pues la tabla
            # la tabla puede no tener autonumérico. En SQL Server es IDENTITY.
            r = self.g.ejecutar(f"SELECT COALESCE(MAX({pk}), 0) + 1 AS siguiente FROM {t}")
            if not r["estado"]:
                self._error(r)
                return
            cols.insert(0, pk)
            vals.insert(0, r["registros"][0]["siguiente"])

        marcadores = ", ".join([self.g.ph] * len(cols))
        sql = f"INSERT INTO {t} ({', '.join(cols)}) VALUES ({marcadores})"
        r = self.g.ejecutar(sql, tuple(vals))
        self._resultado(r, "Registro insertado correctamente.")

    def actualizar(self):
        id_val = self._id_valor()
        if id_val is None:
            QMessageBox.warning(self, "Selecciona un registro", "Haz clic en una fila de la tabla para editarla.")
            return
        vals = self._valores()
        if vals is None:
            return
        t = self.g.nom(self.cfg["tabla"])
        pk = self.g.nom(self.cfg["pk"])
        sets = ", ".join(f"{self.g.nom(c[2])} = {self.g.ph}" for c in self.campos)
        sql = f"UPDATE {t} SET {sets} WHERE {pk} = {self.g.ph}"
        r = self.g.ejecutar(sql, tuple(vals + [id_val]))
        self._resultado(r, "Registro actualizado correctamente.")

    def eliminar(self):
        id_val = self._id_valor()
        if id_val is None:
            QMessageBox.warning(self, "Selecciona un registro", "Haz clic en una fila de la tabla para eliminarla.")
            return
        resp = QMessageBox.question(self, "Confirmar", f"¿Eliminar el registro con ID {id_val}?")
        if resp != QMessageBox.StandardButton.Yes:
            return
        t = self.g.nom(self.cfg["tabla"])
        pk = self.g.nom(self.cfg["pk"])
        sql = f"DELETE FROM {t} WHERE {pk} = {self.g.ph}"
        r = self.g.ejecutar(sql, (id_val,))
        # Si el registro tiene datos relacionados, la BD rechaza el DELETE (IntegrityError)
        self._resultado(r, "Registro eliminado correctamente.")

    # ------------------------------------------------------------------
    # Interfaz
    # ------------------------------------------------------------------
    def cargar_fila(self):
        """Al seleccionar una fila, pasa sus datos al formulario."""
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        self.txt_id.setText(self.tabla.item(fila, 0).text())
        for j, (clave, *_) in enumerate(self.campos, start=1):
            self.entradas[clave].setText(self.tabla.item(fila, j).text())

    def limpiar(self):
        self.txt_id.clear()
        for campo in self.entradas.values():
            campo.clear()
        self.tabla.clearSelection()


# =====================================================================
# VENTANA PRINCIPAL CON EL MENÚ
# =====================================================================
class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Recursos Materiales ITJ - Catálogos")
        self.resize(950, 650)
        self.gestor = None

        barra = self.menuBar()

        # Menú Conexión: elegir motor de base de datos
        menu_con = barra.addMenu("Conexión")
        for texto, motor in [("PostgreSQL", "pg"), ("SQL Server", "ss")]:
            accion = QAction(texto, self)
            accion.triggered.connect(lambda _, m=motor: self.conectar(m))
            menu_con.addAction(accion)

        # Un menú por grupo: "Catálogos" (tablas maestras) y "Movimientos"
        self.menus = []
        for grupo in ("Catálogos", "Movimientos"):
            menu = barra.addMenu(grupo)
            for nombre, cfg in CATALOGOS.items():
                if cfg["grupo"] == grupo:
                    accion = QAction(nombre, self)
                    accion.triggered.connect(lambda _, n=nombre: self.abrir_catalogo(n))
                    menu.addAction(accion)
            self.menus.append(menu)
        self._habilitar(False)  # se habilitan al conectar

        menu_sal = barra.addMenu("Salir")
        accion_salir = QAction("Cerrar aplicación", self)
        accion_salir.triggered.connect(self.close)
        menu_sal.addAction(accion_salir)

        self._bienvenida()

    def _habilitar(self, estado):
        for m in self.menus:
            m.setEnabled(estado)

    def _bienvenida(self):
        etiqueta = QLabel("Selecciona un motor en el menú «Conexión» y luego abre un catálogo o movimiento.")
        etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(etiqueta)

    def conectar(self, motor):
        if self.gestor:
            self.gestor.cerrar()
            self.gestor = None
        self._habilitar(False)
        self._bienvenida()

        nombre = "PostgreSQL" if motor == "pg" else "SQL Server"
        try:
            g = Gestor(motor)
        except ImportError as e:
            QMessageBox.critical(self, "Falta una librería", f"No se pudo cargar el conector de {nombre}:\n{e}")
            return
        if not g.conectar():
            QMessageBox.critical(self, "Conexión", f"No fue posible conectar con {nombre}.\nRevisa tu archivo .env.")
            return

        self.gestor = g
        self._habilitar(True)
        self.statusBar().showMessage(f"Conectado a {nombre}")

    def abrir_catalogo(self, nombre):
        self.setCentralWidget(CatalogoWidget(nombre, CATALOGOS[nombre], self.gestor))

    def closeEvent(self, evento):
        if self.gestor:
            self.gestor.cerrar()
        evento.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())