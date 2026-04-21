# -*- coding: utf-8 -*-
"""Минимальный MySQL-коннект для Драконоборца (self-contained)."""
import os
import pymysql
from dotenv import load_dotenv

# .env лежит в корне dragonslayer/
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))


def get_conn():
    return pymysql.connect(
        host=os.environ['DB_HOST'],
        port=int(os.environ['DB_PORT']),
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        database=os.environ['DB_NAME'],
        connect_timeout=30,
        read_timeout=120,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
