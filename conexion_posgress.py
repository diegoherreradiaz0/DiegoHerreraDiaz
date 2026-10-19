import psycopg2
import json
import os
from dotenv import load_dotenv

# Carga las variables del archivo .env
load_dotenv()


class ConexionPostgres:

    def __init__(self):
        self.server = os.environ.get("server_nameP")
        self.port = os.environ.get("portP", "5432")
        self.database_name = os.environ.get("database_nameP")
        self.user = os.environ.get("userP")
        self.password = os.environ.get("passwordP")

        self.cnx = None
        self.cursor = None

    def crear_conexion(self):
        try:
            self.cnx = psycopg2.connect(
                host=self.server,
                port=self.port,
                dbname=self.database_name,
                user=self.user,
                password=self.password
            )
            self.cursor = self.cnx.cursor()
            self.cursor.execute("SET search_path TO public;")
            
            print(f"--- CONECTADO ---")
            print(f"Host: {self.server} | Puerto: {self.port} | BD: {self.database_name} | Usuario: {self.user}")
            return self.cnx
        except UnicodeDecodeError:
            # PostgreSQL rechazó la conexión, pero su mensaje en español
            # no se puede leer como UTF-8. Normalmente es contraseña,
            # puerto o nombre de base de datos incorrectos.
            print(f"error al conectarse al servidor {self.server}")
            print("Revisa usuario, contraseña, puerto y nombre de la base de datos")
            self.cnx = None
            self.cursor = None
            return None
        except psycopg2.Error as e:
            print(f"error al conectarse al servidor {self.server}")
            print(e)
            self.cnx = None
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
                self.cursor.execute(sql, parametros)
            else:
                self.cursor.execute(sql)

            # Identificar operación
            tipo = sql.strip().split()[0].upper()

            # SELECT
            if tipo == "SELECT":
                columnas = []
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
                    default=str,  # Si no sabe cómo convertir, aplica str()
                    ensure_ascii=False  # Para caracteres latinoamericanos
                )

            # INSERT
            elif tipo == "INSERT":
                filas = self.cursor.rowcount
                self.cnx.commit()
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
        except psycopg2.IntegrityError as e:
            if self.cnx:
                self.cnx.rollback()  # Deshace los movimientos
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
        except psycopg2.ProgrammingError as e:
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
        except psycopg2.Error as e:
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

    # Método cerrar conexión
    def cerrar_conexion(self):
        try:
            if self.cursor:
                self.cursor.close()
                self.cursor = None
            if self.cnx:
                self.cnx.close()
                self.cnx = None

            print(f"se ha cerrado la conexion con el servidor {self.server}")
            return True
        except psycopg2.Error as e:
            print("error al desconectarse del servidor de base de datos")
            print(e)
            return False


if __name__ == '__main__':
        conn_postgres = ConexionPostgres()
        conn_postgres.crear_conexion()
        sql = """
                SELECT C.company_name, O.order_id, P.product_name
                ,OD.quantity, OD.unit_price, OD.discount, 
                ((OD.quantity * OD.unit_price) - (OD.quantity * OD.unit_price * OD.discount)) AS subtotal
                FROM customers C
                INNER JOIN orders O ON C.customer_id = O.customer_id
                INNER JOIN order_details OD ON O.order_id = OD.order_id
                INNER JOIN products P ON OD.product_id = P.product_id
                WHERE O.order_id = %(order_id)s
            """
        parametros = {"order_id": 10248}
        result = json.loads(conn_postgres.ejecutar_consulta(sql, parametros))
        conn_postgres.cerrar_conexion()
        for r in result["registros"]:
            print(r)
            print()