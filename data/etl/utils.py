import os
import sqlite3
import pandas as pd


def _database_path() -> str:
    """
    Returns the absolute path to the SQLite database.
    Creates an empty database file if it does not exist.
    """
    script_rel_path = (
        os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()
    )
    db_path = os.path.join(
        script_rel_path, "database.db"
    )  # Store in the same directory as script

    # Ensure the database file exists
    if not os.path.exists(db_path):
        open(db_path, "w").close()  # Creates an empty file
        print(f"Empty database created at {db_path}")

    return db_path


def create_empty_database():
    """Creates an empty SQLite database if it doesn't exist."""
    db_path = _database_path()

    # Open a connection to ensure the database file is initialized
    with sqlite3.connect(db_path) as con:
        pass  # No tables are created, just ensuring the database exists


def read_sql_table(table_name: str) -> pd.DataFrame:
    """
    Reads a table from the SQLite database into a Pandas DataFrame.
    Returns an empty DataFrame if the table does not exist.
    """
    with sqlite3.connect(_database_path()) as con:
        try:
            return pd.read_sql(f"SELECT * FROM {table_name}", con)
        except sqlite3.OperationalError:
            print(f"Table '{table_name}' does not exist yet.")
            return pd.DataFrame()


def upsert_df_to_sql_table(table_name: str, df: pd.DataFrame) -> None:
    """
    Dynamically creates the table (if needed) and upserts a Pandas DataFrame into the SQLite database.
    """

    if df.empty:
        print(f"No data to insert for table '{table_name}'.")
        return

    with sqlite3.connect(_database_path()) as con:
        # Ensure the table exists by creating it dynamically using the DataFrame schema
        df.head(0).to_sql(name=table_name, con=con, if_exists="append", index=False)

        # Read existing data
        df_sql = read_sql_table(table_name)

        # Merge new and existing data, removing duplicates
        if not df_sql.empty:
            df_to_write = pd.concat([df, df_sql], ignore_index=True).drop_duplicates()
        else:
            df_to_write = df

        # Write updated data back to SQL
        if not df_to_write.empty:
            df_to_write.to_sql(
                name=table_name, con=con, if_exists="replace", index=False
            )
            print(f"Upserted {df_to_write.shape[0]} rows into '{table_name}'")
        else:
            print(f"No new rows to write for table '{table_name}'.")


# Ensure an empty database exists
create_empty_database()
