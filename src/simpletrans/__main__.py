"""
    Script for calculating absorption coefficient as a function of
    altitude for 6 most abundant GHGs.
    
    
    The main work is handled by the HITRAN api.
    Calculating the absorption coefficients once
    and building a database after that enables much faster
    atmospheric model calculations after initial setup.

    The outputs are stored in a local SQLite database.
    The schema for the database is straightforward, and can be found at:
    weblink.
"""
import os
from simpletrans.hapi_wrapper import *
from simpletrans.database_interaction import *
import sqlite3
import numpy as np
from tqdm import tqdm


def main():

    path = input("Path to store database: ")
    if os.path.exists(path):
        print(
            """Populating 2 local databases,
            \n please be patient this takes a long time.
        """
        )
    else:
        print(
            path,
            """is not a valid path, 
        ensure path is a directory that exists
        """,
        )
    ghg_lbl_download(path)
    database_name = "optical_depth.db"
    conn = create_connection(os.path.join(path, database_name))
    # Use sqlite3 PRAGMA for faster loading
    pragma(conn)
    if conn is not None:
        create_table_gas_sql = """CREATE TABLE IF NOT EXISTS gases (
                                    mol_id integer PRIMARY KEY, 
                                    mol_name text NOT NULL, 
                                    mol_ppm real NOT NULL
                                    );"""
        create_table_abs_coef_sql = """CREATE TABLE IF NOT EXISTS 
        optical_depths (
                                        mol_id INTEGER, 
                                        altitude REAL NOT NULL, 
                                        wave_no  REAL NOT NULL,
                                        optical_depth REAL NOT NULL,
                                        abs_coef REAL NOT NULL,
                                        PRIMARY KEY (mol_id, altitude, 
                                        wave_no),
                                        FOREIGN KEY (mol_id) REFERENCES 
                                        gases (mol_id)
                                    );"""
        create_table(conn, create_table_gas_sql)
        create_table(conn, create_table_abs_coef_sql)
        print("created tables")
    else:
        print("Didnt Work")
    #
    # Populating Gases
    for (mol_name, mol_id), (_, mol_ppm) in zip(
        Ghg.ids.items(), Ghg.ppm.items()
    ):
        try:
            insert_query(
                conn,
                "gases",
                mol_name=mol_name,
                mol_id=mol_id,
                mol_ppm=mol_ppm,
            )
        except sqlite3.IntegrityError:
            query = column_comparison_query(
                conn, "gases", "=", mol_id=mol_id
            )
            if not query:
                print(f"{mol_name} already in database")
    altitudes = np.arange(500, 30500, 1000, dtype=float)
    #
    # Populating optical_depths
    for gas, _id in tqdm(Ghg.ids.items()):
        for alt in tqdm(altitudes, leave=False):
            query = column_comparison_query(
                conn, "optical_depths", "=", altitude=alt, mol_id=_id
            )
            if not query:
                wave_number, od, coef = ghg_od_calculate(gas, alt)
                for nu, tau, coef in zip(wave_number, od, coef):
                    try:
                        insert_query(
                            conn,
                            "optical_depths",
                            mol_id=_id,
                            altitude=alt,
                            wave_no=nu,
                            optical_depth=tau,
                            abs_coef=coef,
                        )
                    except sqlite3.IntegrityError:
                        query = column_comparison_query(
                            conn,
                            "optical_depths",
                            "=",
                            mol_id=_id,
                            altitude=alt,
                            wave_no=nu,
                        )
                        if not query:
                            print(
                                f"""Failed to add \n
                                molecule:{gas} \n
                                altitude:{alt} \n
                                wavenumber:{nu}
                                """
                            )
            else:
                pass
    absolute_path = os.path.abspath(path)
    path_file = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
 "path_to_db.txt"), "w")
    path_file.write(os.path.join(absolute_path, database_name))
    path_file.close()
if __name__ == "__main__":
    main()
