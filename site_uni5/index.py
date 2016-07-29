#!/usr/bin/python3-utf8
# -*- coding: utf-8 -*-

import os
import urllib.parse
import json
import sqlite3
import time
import re
import configparser

from classes.template_engine import TemplateEngine
from classes.galaxy_db import GalaxyDB
from classes.xnova_utils import xnova_authorize, PageDownloader, XNGalaxyParser


def debugprint(obj=None):
    print('Content-Type: text/plain; charset=utf-8')
    print()
    print('MODE={0}'.format(MODE))
    print('QUERY_STRING={0}'.format(QUERY_STRING))
    print('QUERY_PARAMS={0}'.format(str(QUERY_PARAMS)))
    print('AJAX_ACTION={0}'.format(AJAX_ACTION))
    if obj is not None:
        print(str(obj))
    exit()


def output_as_json(obj):
    print('Content-Type: application/json; charset=utf-8')
    print()
    print(json.dumps(obj))


def xn_res_str(n: int) -> str:
    if n is None:
        return '0'
    millions = n // 1000000
    n -= millions * 1000000
    if millions == 0:
        k = n // 1000
        if k > 0:
            return str(k) + 'K'
        return '0'
    k = round(n / 100000)
    if k > 0:
        return str(millions) + '.' + str(k) + 'M'
    return str(millions) + 'M'


QUERY_STRING = ''
QUERY_PARAMS = dict()
if 'QUERY_STRING' in os.environ:
    QUERY_STRING = os.environ['QUERY_STRING']
MODE = ''
AJAX_ACTION = ''
if QUERY_STRING != '':
    QUERY_PARAMS = urllib.parse.parse_qs(QUERY_STRING)
    if 'ajax' in QUERY_PARAMS:
        MODE = 'ajax'
        if len(QUERY_PARAMS['ajax']) > 0:
            AJAX_ACTION = QUERY_PARAMS['ajax'][0]


def req_param(name, def_val=None):
    if len(QUERY_PARAMS) < 1:
        return def_val
    if name in QUERY_PARAMS:
        if len(QUERY_PARAMS[name]) > 0:
            return QUERY_PARAMS[name][0]
    return def_val


def fit_in_range(v: int, lower_range: int, upper_range: int) -> int:
    if v < lower_range:
        v = lower_range
    if v > upper_range:
        v = upper_range
    return v


if AJAX_ACTION == 'grid':
    ret = None
    # player/alliance searches
    # GET /xnova/index.py?ajax=grid&query=minlexx&category=player
    # GET /xnova/index.py?ajax=grid&query=minlexx&category=player&sort=user_name&order=desc
    # inactives searches
    # GET /xnova/index.py?ajax=grid&category=inactives&user_flags=iIGU&gals=12345&s_min=1&s_max=499&min_rank=0
    # parse request
    val = req_param('query')
    cat = req_param('category')
    s_col = req_param('sort')  # may be None
    s_order = req_param('order')  # may be None
    user_flags = req_param('user_flags')
    gals = req_param('gals', '12345')
    s_min = req_param('s_min', '1')
    s_max = req_param('s_max', '499')
    min_rank = req_param('min_rank', '0')
    if (val is not None) and (cat is not None):
        gdb = GalaxyDB()
        val += '%'  # ... WHERE user_name LIKE 'value%'
        if cat == 'player':
            ret = gdb.query_like('user_name', val, s_col, s_order)
        elif cat == 'alliance':
            ret = gdb.query_like(['ally_name', 'ally_tag'], val, s_col, s_order)
    if cat is not None:
        if (cat == 'inactives') and (user_flags is not None):
            # - covert any char in gals to integer
            # - check it is in range [1..5]
            # - do not add any duplicates to list
            gal_ints = []  # resulting list
            for g in gals:
                g = GalaxyDB.safe_int(g)
                g = fit_in_range(g, 1, 5)
                if g not in gal_ints:
                    gal_ints.append(g)
            # covert systems range to ints,
            # make sure s_min is <= s_max
            # make sure values are in range [1..499]
            s_min = GalaxyDB.safe_int(s_min)
            s_max = GalaxyDB.safe_int(s_max)
            if s_min > s_max:
                t = s_min
                s_min = 5
                s_max = t
            s_min = fit_in_range(s_min, 1, 499)
            s_max = fit_in_range(s_max, 1, 499)
            min_rank = GalaxyDB.safe_int(min_rank)
            min_rank = fit_in_range(min_rank, 0, 1000000)
            # go!
            gdb = GalaxyDB()
            ret = gdb.query_inactives(user_flags, gal_ints, s_min, s_max, min_rank, s_col, s_order)
    # fix empty response
    if ret is None:
        ret = dict()
    if not 'rows' in ret:  # ret should have rows
        ret['rows'] = []
    ret['total'] = len(ret['rows'])  # ret should have total count:
    # extra debug data
    ret['QUERY_STRING'] = QUERY_STRING
    output_as_json(ret)
    exit()

if AJAX_ACTION == 'lastactive':
    ret = dict()
    ret['rows'] = []
    ret['total'] = 0
    #
    player_name = req_param('query')
    if (player_name is not None) and (player_name != ''):
        gdb = GalaxyDB()
        planets_info = gdb.query_player_planets(player_name)
        # ret['planets_info'] = planets_info  # checked - this is OK
        # list of dicts [{'g': 1, 's': 23, 'p': 9, ...}, {...}, {...}, ...]
        if len(planets_info) > 0:
            # 1. cookies_dict = xnova_authorize('uni5.xnova.su', 'login', 'password')
            # 2. hope this cookie will live long enough
            # cookies_dict = {
            #    'u5_id': '87',
            #    'u5_secret': 'c...7',
            #    'u5_full': 'N'
            # }
            # 3. read from config file
            cookies_dict = {
                'u5_id': '0',
                'u5_secret': '',
                'u5_full': 'N'
            }
            cfg = configparser.ConfigParser()
            cfgs_read = cfg.read(['config.ini'])
            if 'config.ini' not in cfgs_read:
                ret['error'] = 'Failed to load xnova auth cookies from config.ini'
                output_as_json(ret)
                exit()
            if 'lastactive' not in cfg.sections():
                ret['error'] = 'Cannot find [lastactive] section in config.ini'
                output_as_json(ret)
                exit()
            cookies_dict['u5_id'] = cfg['lastactive']['u5_id']
            cookies_dict['u5_secret'] = cfg['lastactive']['u5_secret']
            #
            dnl = PageDownloader(cookies_dict=cookies_dict)
            gparser = XNGalaxyParser()
            cached_pages = dict()  # coords -> page_content
            for pinfo in planets_info:
                # try to lookup page in a cache, with key 'galaxy,system'
                coords_str = str(pinfo['g']) + ',' + str(pinfo['s'])  # '1,23'
                if coords_str in cached_pages:
                    page_content = cached_pages[coords_str]
                else:
                    page_content = dnl.download_url_path('galaxy/{0}/{1}/'.format(
                        pinfo['g'], pinfo['s']), return_binary=False)
                # seems to work, for now...
                if page_content is None:
                    ret['error'] = 'Failed to download, ' + dnl.error_str
                    ret['rows'] = []
                    break
                else:
                    cached_pages[coords_str] = page_content  # save to cache
                    # ret['page'] = page_content  # checked, galaxy page loaded OK
                    # now need to parse it
                    gparser.clear()
                    gparser.parse_page_content(page_content)
                    galaxy_rows = gparser.unscramble_galaxy_script()
                    if galaxy_rows is None:
                        ret['error'] = 'Failed to parse galaxy page, ' + gparser.error_str
                        ret['rows'] = []
                        break
                    else:
                        # parse OK
                        for planet_row in galaxy_rows:
                            if planet_row is not None:
                                planet_pos = GalaxyDB.safe_int(planet_row['planet'])
                                if planet_pos == pinfo['p']:
                                    ret_row = dict()
                                    ret_row['planet_name'] = planet_row['name']
                                    ret_row['luna_name'] = ''
                                    if planet_row['luna_name'] is not None:
                                        ret_row['luna_name'] = planet_row['luna_name']
                                    ret_row['coords_link'] = '<a href="http://uni5.xnova.su/galaxy/{0}/{1}/">' \
                                        '[{0}:{1}:{2}]</a>'.format(pinfo['g'], pinfo['s'], pinfo['p'])
                                    ret_row['lastactive'] = planet_row['last_active']
                                    ret['rows'].append(ret_row)
            # recalculate total rows count
            ret['total'] = len(ret['rows'])
        pass
    #
    output_as_json(ret)
    exit()

if AJAX_ACTION == 'lastlogs':
    # /xnova/index.py?ajax=lastlogs
    # /xnova/index.py?ajax=lastlogs&value=24&category=hours&nick=Nickname
    #                 category may be 'days'
    cat = req_param('category', 'hours')  # default - hours
    val = int(req_param('value', 24))     # default - 24 hours
    nick = req_param('nick', '')          # default - empty
    #
    tm_now = int(time.time())
    requested_time_interval_hrs = val
    if cat == 'days':
        requested_time_interval_hrs = 24 * val  # specified number of days
    requested_time_interval_secs = requested_time_interval_hrs * 3600
    min_time = tm_now - requested_time_interval_secs
    #
    ret = dict()
    ret['rows'] = []
    # Debug: :)
    # ret['min_time'] = min_time
    # ret['cur_time'] = tm_now
    # ret['requested_time_interval_hrs'] = requested_time_interval_hrs
    log_rows = []
    sqconn = sqlite3.connect('lastlogs5.db')
    cur = sqconn.cursor()
    #
    # check if table 'logs' exists
    cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='logs' AND type='table'")
    rows = cur.fetchall()
    if (len(rows) != 1) or (rows[0][0] != 1):
        ret['rows'] = []
        ret['total'] = 0
        ret['msg'] = 'table not found: logs'
        output_as_json(ret)
        exit()
    #
    if nick != '':
        q = 'SELECT log_id, log_time, attacker, defender, attacker_coords, defender_coords, ' \
            ' total_loss, po_me, po_cry, win_me, win_cry, win_deit ' \
            'FROM logs ' \
            "WHERE (log_time >= ?) AND ((attacker LIKE ?) OR (defender LIKE ?))" \
            'ORDER BY log_time DESC'
        cur.execute(q, (min_time, nick+'%', nick+'%'))
    else:
        q = 'SELECT log_id, log_time, attacker, defender, attacker_coords, defender_coords, ' \
            ' total_loss, po_me, po_cry, win_me, win_cry, win_deit ' \
            'FROM logs ' \
            'WHERE log_time >= ?' \
            'ORDER BY log_time DESC'
        cur.execute(q, (min_time, ))
    for row in cur.fetchall():
        att_c = str(row[4])
        def_c = str(row[5])
        att_c_link = ''
        def_c_link = ''
        m = re.search(r'\[(\d+):(\d+):(\d+)\]', att_c)
        if m is not None:
            coord_g = int(m.group(1))
            coord_s = int(m.group(2))
            att_c_link = 'http://uni5.xnova.su/galaxy/{0}/{1}/'.format(coord_g, coord_s)
        m = re.search(r'\[(\d+):(\d+):(\d+)\]', def_c)
        if m is not None:
            coord_g = int(m.group(1))
            coord_s = int(m.group(2))
            def_c_link = 'http://uni5.xnova.su/galaxy/{0}/{1}/'.format(coord_g, coord_s)
        lrow = dict()
        lrow['log_id'] = '<a href="http://uni5.xnova.su/log/' + str(row[0]) + '/" target="_blank">#' \
                         + str(row[0]) + '</a>'
        lrow['log_time'] = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime(int(row[1])))
        lrow['attacker'] = str(row[2]) + ' <a href="' + att_c_link + '" target="_blank">' + str(row[4]) + '</a>'
        lrow['defender'] = str(row[3]) + ' <a href="' + def_c_link + '" target="_blank">' + str(row[5]) + '</a>'
        lrow['total_loss'] = xn_res_str(row[6])
        lrow['po'] = xn_res_str(row[7]) + ' me, ' + xn_res_str(row[8]) + ' cry'
        lrow['win'] = xn_res_str(row[9]) + ' me, ' + xn_res_str(row[10]) + ' cry, ' + xn_res_str(row[11]) + ' deit'
        log_rows.append(lrow)
    ret['rows'] = log_rows
    ret['total'] = len(log_rows)
    output_as_json(ret)
    exit()

if AJAX_ACTION == 'gmap_population':
    gdb = GalaxyDB()
    population_data = []
    for g in range(1, 5):  # includes 0, not includes 5: [0..4]
        for s in range(1, 500):  # [1..499]
            population_data.append(gdb.query_planets_count(g, s))
    output_as_json(population_data)
    exit()


template = TemplateEngine({
    'TEMPLATE_DIR': './html',
    'TEMPLATE_CACHE_DIR': './cache'})
template.output('index.html')
