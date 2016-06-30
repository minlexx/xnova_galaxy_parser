import sys
import os
import sqlite3
import re
import argparse
import logging

import requests
import requesocks

from xnova import xn_logger
from xnova.xn_auth import xnova_authorize
from xnova.xn_page_cache import XNovaPageCache
from xnova.xn_page_dnl import XNovaPageDownload

from xnova.lastlogs_utils import safe_int, LLDb


logger = xn_logger.get(__name__, debug=True)


def main():
    # parse command line
    ap = argparse.ArgumentParser(description='XNova Uni5 combat logs parser.')
    ap.add_argument('--version', action='version', version='%(prog)s 0.2')
    ap.add_argument('--debug', action='store_true', help='Enable debug logging.')
    ap.add_argument('--login', nargs=1, default='', type=str, metavar='LOGIN',
                    help='Login to use to authorize in XNova game')
    ap.add_argument('--password', nargs=1, default='', type=str, metavar='PASS',
                    help='Password to use to authorize in XNova game')
    ap.add_argument('--dbfile', nargs=1, default='lastlogs5.db', type=str, metavar='DBFILE',
                    help='Name of sqlite3 db file to store logs data. Default is "lastlogs5.db"')
    ap_result = ap.parse_args()

    if ap_result.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug('DEBUG enabled')

    pass


if __name__ == '__main__':
    main()
    sys.exit(0)
