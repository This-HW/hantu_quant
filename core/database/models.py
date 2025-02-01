# database.py

import sqlite3
import pandas as pd
from config import DB_NAME


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME)
        self.create_table()

    def create_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS price_data (
            Date TEXT,
            Open REAL,
            High REAL,
            Low REAL,
            Close REAL,
            Volume INTEGER,
            Code TEXT
        )
        """
        self.conn.execute(query)
        self.conn.commit()

    def save_price_data(self, df, code):
        df = df.copy()
        df['Code'] = code
        df.reset_index(inplace=True)
        df.to_sql('price_data', self.conn, if_exists='append', index=False)

    def get_price_data(self, code):
        query = f"SELECT * FROM price_data WHERE Code='{code}'"
        df = pd.read_sql(query, self.conn, parse_dates=['Date'])
        df.set_index('Date', inplace=True)
        return df
