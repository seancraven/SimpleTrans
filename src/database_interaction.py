from typing import Any
import sqlite3
from sqlite3 import Error



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
        table: table to query.
        operator: WHERE column {operator} value. The comparison operator
            for a SQL statement.

    *Kwargs:
        columns: column_name=value, for the comparison operator.
    Returns:
        tuple: values from table.
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

