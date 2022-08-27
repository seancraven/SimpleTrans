from typing import Any
import sqlite3
from sqlite3 import Error
from simpletrans.hapi_wrapper import ghg_od_calculate
import sys
import os
import pandas as pd
import tqdm


class HiddenPrints:
    """Suppresses prints to console"""

    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout


with HiddenPrints():
    import hapi


def pragma(connection: sqlite3.Connection):
    """Function to improve performance of sqlite database"""
    connection.execute("PRAGMA journal_mode = OFF;")
    connection.execute("PRAGMA synchronous = 0;")
    connection.execute("PRAGMA cache_size = 1000000;")  # give it a GB
    connection.execute("PRAGMA locking_mode = EXCLUSIVE;")
    connection.execute("PRAGMA temp_store = MEMORY;")


def create_connection(db_file: str):
    """
    Creates a connection to database object.

    Args:
        db_file (str): /path/to/database/name.db

    Returns:
        database connection object:
    """
    connection = None
    try:
        connection = sqlite3.connect(db_file)
        return connection
    except Error as e:
        print(e)


def create_table(connection: sqlite3.Connection, create_table_sql: str):
    """
    Creates a table from sql statement.

    Args:
        connection: Database to create table in.
        create_table_sql: SQL command to create table string.
    """
    try:
        c = connection.cursor()
        c.execute(create_table_sql)
    except Error as e:
        print(e)


def insert_query(
    connection: sqlite3.Connection, table: str, **values: Any
):
    """
    Adds an entry to a tabel.

    Args:
        connection: Database to insert into
        table: Table of database to insert into.
    Keyword Args:
        values: of the form column=entry. The entry must have the same
        type as specified in the database.
    Returns:
        int: Last row number appended to table
    """

    sql = f"INSERT INTO {table}"
    columns = "("
    value_var = "("
    for column in values.keys():
        columns += column + ","
        value_var += "?,"
    columns = columns[:-1] + ")"
    value_var = value_var[:-1] + ");"
    sql += columns + "VALUES" + value_var
    try:
        cur = connection.cursor()
        cur.execute(sql, list(values.values()))
        connection.commit()
        return cur.lastrowid
    except Error as e:
        print(e)


def column_comparison_query(
    connection: sqlite3.Connection,
    table: str,
    operator: str,
    **columns_val,
):
    """
    Function that performs a query on a table with the op, returns all
    columns of a row that obeys the query conditions.

    Args:
        connection: Database to query.
        Table: table to query.
        Operator: WHERE column {operator} value. The comparison operator
            for a SQL statement.

    *Kwargs:
        columns: column_name=value, for the comparison operator.
    Returns:
        tuple: values from the table.
    """
    vals = []
    sql = f"SELECT * from {table} WHERE"
    for i, (column, value) in enumerate(columns_val.items()):
        if i != 0:
            sql += " and"
        sql += f" {column} {operator} ?"
        vals.append(value)
    sql += ";"
    try:
        cur = connection.cursor()
        cur.execute(sql, vals)
        query_result = cur.fetchall()
        return query_result
    except Error as e:
        print(e)


def default_db() -> sqlite3.Connection:
    """
    Helper function to form connection to database maid in __main__.py.
    If there is a problem it crashes.
    Returns:
        Database connection object.
    """
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(parent_dir, "path_to_db.txt"), "r") as f:
        path = f.read()
        if os.path.isfile(path):
            return sqlite3.connect(path)
        else:
            print(
                """inspect path_to_db.txt, to ensure that the path is
                valid.
                """
            )
            raise FileNotFoundError


def add_gas(mol_name, mol_id, mol_ppm, connection=None):
    if not connection:
        connection=default_db()
    try:
        insert_query(
            connection,
            "gases",
            mol_id=mol_id,
            mol_name=mol_name,
            mol_ppm=mol_ppm,
        )
    except sqlite3.IntegrityError:
        query = column_comparison_query(connection, "gases", "=", mol_id=mol_id)
        if not query:
            print(f"{mol_name} already in database")
    sql_alt_query = "SELECT DISTINCT altitude from optical_depths"
    alts = pd.read_sql_query(sql_alt_query, connection)
    hapi.db_begin("../../spectral_line.db")
    hapi.fetch(mol_name, mol_id, 1, 0, 4000)
    for alt in tqdm(alts):
        query = column_comparison_query(
            connection, "optical_depths", "=", altitude=alt, mol_id=mol_id
        )
        if not query:
            wave_number, od, coef = ghg_od_calculate(
                mol_name, alt, ghg_ppm=mol_ppm
            )
            for nu, tau, coef in zip(wave_number, od, coef):
                try:
                    insert_query(
                        connection,
                        "optical_depths",
                        mol_id=mol_id,
                        altitude=alt,
                        wave_no=nu,
                        optical_depth=tau,
                        abs_coef=coef,
                    )
                except sqlite3.IntegrityError:
                    query = column_comparison_query(
                        connection,
                        "optical_depths",
                        "=",
                        mol_id=mol_id,
                        altitude=alt,
                        wave_no=nu,
                    )
                    if not query:
                        print(
                            f"""Failed to add \n
                            molecule:{mol_name} \n
                            altitude:{alt} \n
                            wavenumber:{nu}
                            """
                        )
            else:
                pass
