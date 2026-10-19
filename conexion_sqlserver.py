import mssql_python
import json
import os
from dotenv import load_dotenv

load_dotenv()

class ConecionSqlServer:

    def __init__(self):
        self.server =  os.environ.get("server_name")
        self.database_name = os.environ.get("database_name")
        self.user = os.environ.get("user")
        self.password = os.environ.get("password")

        self.cnx = None #
        self.cursor = None #

    def crear_conexion(self):
        try:
            cadena_conexion = (
                f"Server={self.server};"
                f"Database={self.database_name};"
                f"uid={self.user};"
                f"pwd={self.password};"
                "Encrypt=yes;"
                "TrustServerCertificate=yes;"
            )

            self.cnx= mssql_python.connect(cadena_conexion)
            self.cursor = self.cnx.cursor()
            print(f"conectado al servidor {self.server}")
            return self.cnx
        except mssql_python.Error as e:
            print(f"error al conectarse al servidor {self.server}")
            print(e)
            self.cnx= None
            self.cursor = None
            return None 

    def ejecutar_consulta(self, sql, parametros=None):
        try:
            # Verificar conexión
            if self.cnx is None:
                # Intento conectarme
                if self.crear_conexion() is None:
                    return json.dumps(
                        {
                            "estado": False,
                            "mensaje": "No fue posible establecer la conexión"
                        },
                        ensure_ascii=False
                    )
 
            # Ejecutar consulta
            if parametros:
                self.cursor.execute(
                    sql,
                    parametros
                )
            else:
                self.cursor.execute(sql)
 
            # Identificar operación
            tipo = sql.strip().split()[0].upper()
            # SELECT
            if tipo == "SELECT":
                columnas=[]
                for columna in self.cursor.description:
                    columnas.append(columna[0])
 
                # Obtener registros
                registros = self.cursor.fetchall()
 
                resultado = []
                for registro in registros:
                    fila = {}
                    for i, valor in enumerate(registro):
                        fila[columnas[i]] = valor
                    resultado.append(fila)
 
                return json.dumps(
                    {
                        "estado": True,
                        "tipo": "SELECT",
                        "registros": resultado
                    },
                    default=str, # Si no sabe como convertir, aplicale la funcion str()
                    ensure_ascii=False # Para caracteres latinoamericanos
                )
            # INSERT
            elif tipo == "INSERT":
                filas = self.cursor.rowcount # Obtine el numero de rgistros afectados
                self.cnx.commit() # Comete la transacción
                return json.dumps(
                    {
                        "estado": True,
                        "tipo": "INSERT",
                        "mensaje": "Registro insertado correctamente",
                        "filas_afectadas": filas
                    },
                    ensure_ascii=False
                )
            # UPDATE
            elif tipo == "UPDATE":
                filas = self.cursor.rowcount
                self.cnx.commit()
                return json.dumps(
                    {
                        "estado": True,
                        "tipo": "UPDATE",
                        "mensaje": "Registro actualizado correctamente",
                        "filas_afectadas": filas
                    },
                    ensure_ascii=False
                )
            # DELETE
            elif tipo == "DELETE":
                filas = self.cursor.rowcount
                self.cnx.commit()
                return json.dumps(
                    {
                        "estado": True,
                        "tipo": "DELETE",
                        "mensaje": "Registro eliminado correctamente",
                        "filas_afectadas": filas
                    },
                    ensure_ascii=False
                )
            # OTRAS OPERACIONES
            else:
                filas = self.cursor.rowcount
                self.cnx.commit()
                return json.dumps(
                    {
                        "estado": True,
                        "tipo": tipo,
                        "mensaje": "Consulta ejecutada correctamente",
                        "filas_afectadas": filas
                    },
                    ensure_ascii=False
                )
        # ERROR DE INTEGRIDAD
        except mssql_python.IntegrityError as e:
            if self.cnx:
                self.cnx.rollback() #desace los movimientos
            return json.dumps(
                {
                    "estado": False,
                    "tipo": "IntegrityError",
                    "mensaje": "Violación de integridad en la base de datos",
                    "error": str(e)
                },
                ensure_ascii=False
            )
        # ERROR DE PROGRAMACIÓN SQL
        except mssql_python.ProgrammingError as e:
            if self.cnx:
                self.cnx.rollback()
            return json.dumps(
                {
                    "estado": False,
                    "tipo": "ProgrammingError",
                    "mensaje": "Error en la consulta SQL",
                    "error": str(e)
                },
                ensure_ascii=False
            )
        # ERROR GENERAL
        except mssql_python.Error as e:
            if self.cnx:
                self.cnx.rollback()
            return json.dumps(
                {
                    "estado": False,
                    "tipo": "DatabaseError",
                    "mensaje": "Error en la base de datos",
                    "error": str(e)
                },
                ensure_ascii=False
            )
        # ERROR DE PYTHON
        except Exception as e:
            if self.cnx:
                self.cnx.rollback()
            return json.dumps(
                {
                    "estado": False,
                    "tipo": "Error",
                    "mensaje": "Error inesperado",
                    "error": str(e)
                },
                ensure_ascii=False
            )
#metodo cerrar conexion
    def cerrar_conexion(self):
        try:
            if self.cursor:
                self.cursor.close()
                self.cursor = None
            if self.cnx:
                self.cnx.close()
                self.cnx = None
                
            print(f"se ha cerrado la conexion con el servidor{self.server}")
            return True
        except mssql_python.Error as e:
            print(f"error al desconectarse del ervidor de base de datos")
            print(e)
            return False


if __name__ == '__main__':
    cnn = ConecionSqlServer()
    cnn.crear_conexion()
    sql_select = """SELECT * FROM Customers"""
    resultado = cnn.ejecutar_consulta(sql_select)
    cnn.cerrar_conexion()
    #convertir el resultado en json
    resultados = json.loads(resultado)
    for r in resultado ["registros"]:
        if r["CustomerID"] == 'ANTR1':
            print(r)
            break
    
