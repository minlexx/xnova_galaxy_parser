#!/usr/bin/python3
import sys
import time
import sqlite3
import json
import argparse
import re
# 3rd party, not used right here, but used by sub-modules anyway
import requests
import execjs
# local includes
from xnova import xn_logger
from xnova.xn_page_cache import XNovaPageCache
from xnova.xn_page_dnl import XNovaPageDownload
from xnova.xn_parser_galaxy import GalaxyParser

# globals
g_logger = xn_logger.get(__name__, debug=True)
g_db_filename = 'online_checker.db'

g_sqlite = sqlite3.connect(g_db_filename)
g_sqlite.row_factory = sqlite3.Row


class GalaxyDB:
    def __init__(self):
        self._db = sqlite3.connect('galaxy.db')
        # sqlite3.Row allows to use names columns (row['user_id']) instead of numbers
        self._db.row_factory = sqlite3.Row

    def close(self):
        self._db.close()

    def find_player_by_name(self, player_name: str) -> tuple:
        q = """
        SELECT user_id, user_name FROM planets WHERE user_name=? LIMIT 1
        """
        cur = self._db.cursor()
        cur.execute(q, (player_name, ))
        rows = cur.fetchall()
        cur.close()
        for row in rows:
            p_tuple = (row['user_id'], row['user_name'])
            return p_tuple
        g_logger.warn('GalaxyDB: cannot find player [{0}]'.format(player_name))
        return None

    def find_player_planets(self, player_id: int) -> list:
        pass


g_gdb = GalaxyDB()


def check_database_tables():
    cur = g_sqlite.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    rows = cur.fetchall()
    existing_tables = list()
    for row in rows:
        existing_tables.append(row[0])
    if 'watched_players' not in existing_tables:
        g_logger.info('DB: Creating table watched_players...')
        q = """
            CREATE TABLE watched_players(
              player_id INT PRIMARY KEY, \n
              player_name TEXT, \n
              add_time INT \n
            )"""
        cur.execute(q)
        g_sqlite.commit()
    if 'players_online' not in existing_tables:
        g_logger.info('DB: Creating table players_online...')
        q = """
            CREATE TABLE players_online(
              player_id INT PRIMARY KEY, \n
              online_time INT, \n
              num_planets INT \n
            )"""
        cur.execute(q)
        g_sqlite.commit()
    cur.close()
    g_logger.info('DB init complete')


def add_watched_player(player_id: int, player_name: str):
    cur = g_sqlite.cursor()
    # check maybe player is already added
    q = """
    SELECT player_id, player_name FROM watched_players
    WHERE player_id=?
    """
    cur.execute(q, (player_id, ))
    rows = cur.fetchall()
    if len(rows) > 0:
        g_logger.info('Player {0} #{1} is already watched.'.format(player_name, player_id))
        return True
    q = """
    INSERT INTO watched_players (player_id, player_name, add_time)
    VALUES (?, ?, ?)
    """
    cur.execute(q, (player_id, player_name, int(time.time())))
    g_sqlite.commit()
    cur.close()
    g_logger.info('Player {0} #{1} added to watched.'.format(player_name, player_id))


def get_watched_players_ids() -> list:
    cur = g_sqlite.cursor()
    q = "SELECT player_id FROM watched_players ORDER BY add_time"
    cur.execute(q)
    rows = cur.fetchall()
    cur.close()
    ret = []
    for row in rows:
        ret.append(int(row['player_id']))
    return ret


##############################################################################################


def test_add_watched_player(player_name: str):
    p_tuple = g_gdb.find_player_by_name(player_name)
    if p_tuple is None:
        g_logger.error('Failed!')
        sys.exit(1)
    player_id = int(p_tuple[0])
    add_watched_player(player_id, player_name)


def test():
    test_add_watched_player('Павел')

    wpids = get_watched_players_ids()
    for wpid in wpids:
        pass


check_database_tables()
test()

g_sqlite.close()
g_gdb.close()
