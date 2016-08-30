#!/usr/bin/python3
import sys
import time
import sqlite3
import json
import argparse
import re
import six
import unittest

# 3rd party, not used right here, but used by sub-modules anyway
import requests
import execjs

# local includes
from xnova import xn_logger
from xnova.xn_page_cache import XNovaPageCache
from xnova.xn_page_dnl import XNovaPageDownload
from xnova.xn_parser_galaxy import GalaxyParser
from xnova.galaxy_db import GalaxyDB


class OnlineDB:
    def __init__(self, db_filename):
        self.db = sqlite3.connect(db_filename)
        self.db.row_factory = sqlite3.Row

    def close(self):
        self.db.close()
        del self.db

    def check_database_tables(self):
        cur = self.db.cursor()
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
            self.db.commit()
        if 'players_online' not in existing_tables:
            g_logger.info('DB: Creating table players_online...')
            q = """
                CREATE TABLE players_online(
                  player_id INT PRIMARY KEY, \n
                  online_time INT, \n
                  num_planets INT \n
                )"""
            cur.execute(q)
            self.db.commit()
        cur.close()
        g_logger.info('DB init complete')

    def add_watched_player(self, player_id: int, player_name: str):
        cur = self.db.cursor()
        # check maybe player is already added
        q = """
        SELECT player_id, player_name FROM watched_players
        WHERE player_id=?
        """
        cur.execute(q, (player_id,))
        rows = cur.fetchall()
        if len(rows) > 0:
            g_logger.info('Player {0} #{1} is already watched.'.format(player_name, player_id))
            return True
        q = """
        INSERT INTO watched_players (player_id, player_name, add_time)
        VALUES (?, ?, ?)
        """
        cur.execute(q, (player_id, player_name, int(time.time())))
        self.db.commit()
        cur.close()
        g_logger.info('Player {0} #{1} added to watched.'.format(player_name, player_id))

    def get_watched_players_ids(self) -> list:
        cur = self.db.cursor()
        q = "SELECT player_id FROM watched_players ORDER BY add_time"
        cur.execute(q)
        rows = cur.fetchall()
        cur.close()
        ret = []
        for row in rows:
            ret.append(int(row['player_id']))
        return ret


# globals
g_logger = xn_logger.get(__name__, debug=True)
g_db_filename = 'online_checker.db'

g_gdb = GalaxyDB()
g_odb = OnlineDB(g_db_filename)
g_odb.check_database_tables()


##############################################################################################


class ODBTests(unittest.TestCase):
    def test_add_watched_player(self):
        player_name = 'DemonDV'
        p_tuple = self.gdb.find_player_by_name(player_name)
        if p_tuple is None:
            g_logger.error('Failed!')
        else:
            player_id = int(p_tuple[0])
            self.odb.add_watched_player(player_id, player_name)
        self.assertIsNotNone(p_tuple)

    def test_get_watched_players(self):
        wpids = self.odb.get_watched_players_ids()
        for wpid in wpids:
            print(wpid)
        self.assertIsNotNone(wpids)

    def setUp(self):
        self.gdb = GalaxyDB()
        self.odb = OnlineDB('online_checker.db')
        self.odb.check_database_tables()

    def tearDown(self):
        self.odb.close()
        self.gdb.close()

    def runTest(self):
        self.test_add_watched_player()
        self.test_get_watched_players()


def main():
    ts = unittest.TestSuite()
    tr = unittest.TestResult(verbosity=True)
    ts.addTest(ODBTests())
    ts.run(tr, debug=True)


if __name__ == '__main__':
    main()

g_odb.close()
g_gdb.close()
