#!/usr/bin/python3-utf8
# -*- coding: utf-8 -*-

import os
import urllib.parse
import json
import sqlite3
import time
import re
from mako.lookup import TemplateLookup
from mako import exceptions


class TemplateEngine:
    def __init__(self, config: dict):
        """
        Constructor
        :param config: dict with keys:
         'TEMPLATE_DIR' - directory where to read template html files from
         'TEMPLATE_CACHE_DIR' - dir to store compiled templates in
        :return: None
        """
        if 'TEMPLATE_DIR' not in config:
            config['TEMPLATE_DIR'] = '.'
        if 'TEMPLATE_CACHE_DIR' not in config:
            config['TEMPLATE_CACHE_DIR'] = '.'
        params = {
            'directories':      config['TEMPLATE_DIR'],
            'module_directory': config['TEMPLATE_CACHE_DIR'],
            'input_encoding':   'utf-8',
            # 'output_encoding':   'utf-8',
            # 'encoding_errors':  'replace',
            'strict_undefined': True
        }
        self._lookup = TemplateLookup(**params)
        self._args = dict()
        self._headers_sent = False

    def assign(self, vname, vvalue):
        """
        Assign template variable value
        :param vname: - variable name
        :param vvalue: - variable value
        :return: None
        """
        self._args[vname] = vvalue

    def unassign(self, vname):
        """
        Unset template variablr
        :param vname: - variable name
        :return: None
        """
        if vname in self._args:
            self._args.pop(vname)

    def render(self, tname):
        """
        Primarily internal function, renders specified template file
        and returns result as string, ready to be sent to browser.
        Called by TemplateEngine.output(tname) automatically.
        :param tname: - template file name
        :return: rendered template text
        """
        tmpl = self._lookup.get_template(tname)
        return tmpl.render(**self._args)

    def output(self, tname):
        """
        Renders html template file (using TemplateEngine.render(tname).
        Then outputs all to browser: sends HTTP headers (such as Content-type),
        then sends rendered template. Includes Mako exceptions handler
        :param tname: - template file name to output
        :return: None
        """
        if not self._headers_sent:
            print('Content-Type: text/html')
            print()
            self._headers_sent = True
        # MAKO exceptions handler
        try:
            rendered = self.render(tname)
            # python IO encoding mut be set to utf-8 (see ../index.py header for details)
            print(rendered)
        except exceptions.MakoException:
            print(exceptions.html_error_template().render())


class GalaxyDB:

    PLANET_TYPE_PLANET = 1
    PLANET_TYPE_BASE = 5

    def __init__(self):
        self._conn = sqlite3.connect('galaxy5.db')
        self._conn.row_factory = sqlite3.Row
        self._cur = self._conn.cursor()
        self._log_queries = False

    def create_query(self, where_clause=None, sort_col=None, sort_order=None):
        q = 'SELECT g,s,p, \n' \
            '  planet_id, planet_name, planet_type, planet_metal, planet_crystal, planet_destroyed, \n' \
            '  luna_id, luna_name, luna_diameter, luna_destroyed, \n' \
            '  user_id, user_name, user_rank, user_onlinetime, user_banned, user_ro, user_race, \n' \
            '  ally_id, ally_name, ally_tag, ally_members \n' \
            ' FROM planets'
        if where_clause is not None:
            q += ' \n'
            q += where_clause
        # sort, order
        q += '\n ORDER BY '
        # fix invalid input
        if sort_order is not None:
            if sort_order not in ['asc', 'desc']:
                sort_order = None
        if sort_col is not None:
            if sort_col not in ['planet_name', 'planet_type', 'user_name', 'user_rank', 'ally_name', 'luna_name']:
                sort_col = None
        # append sorting
        if sort_col is not None:
            q += sort_col
            if sort_order is not None:
                q += ' '
                q += sort_order
            q += ', '
        q += 'g ASC, s ASC, p ASC'  # by default, always sort by coords
        # log query
        if self._log_queries:
            try:
                with open('queries.log', mode='at', encoding='UTF-8') as f:
                    f.write(q)
                    f.write('\n')
            except IOError:
                pass
        return q

    @staticmethod
    def safe_int(val):
        if val is None:
            return 0
        try:
            r = int(val)
        except ValueError:
            r = 0
        return r

    @staticmethod
    def safe_str(val):
        if val is None:
            return ''
        return str(val)

    def _rows_to_res_list(self):
        rows_list = []
        rows = self._cur.fetchall()
        for row in rows:
            r = dict()
            r['coords'] = '[{0}:{1}:{2}]'.format(row['g'], row['s'], row['p'])
            r['coords_link'] = '<a href="http://uni5.xnova.su/galaxy/{3}/{4}/" target="_blank">' \
                               '[{0}:{1}:{2}]</a>'.format(row['g'], row['s'], row['p'],
                                                          row['g'], row['s'])
            r['planet_id'] = GalaxyDB.safe_int(row['planet_id'])
            r['planet_name'] = GalaxyDB.safe_str(row['planet_name'])
            r['planet_type'] = GalaxyDB.safe_int(row['planet_type'])
            r['user_id'] = GalaxyDB.safe_int(row['user_id'])
            r['user_name'] = GalaxyDB.safe_str(row['user_name'])
            r['user_rank'] = GalaxyDB.safe_int(row['user_rank'])
            r['user_onlinetime'] = GalaxyDB.safe_int(row['user_onlinetime'])
            r['user_banned'] = GalaxyDB.safe_int(row['user_banned'])
            r['user_ro'] = GalaxyDB.safe_int(row['user_ro'])
            # fix user name to include extra data
            user_flags = ''
            if r['user_ro'] > 0:
                user_flags += 'U'
            if r['user_banned'] > 0:
                user_flags += 'G'
            if r['user_onlinetime'] == 1:
                user_flags += 'i'
            if r['user_onlinetime'] == 2:
                user_flags += 'I'
            if user_flags != '':
                r['user_name'] += ' (' + user_flags + ')'
            # user race and race icon
            r['user_race'] = GalaxyDB.safe_int(row['user_race'])
            r['user_race_img'] = '<img border="0" src="css/icons/race{0}.png" width="18" />'.format(r['user_race'])
            r['ally_name'] = GalaxyDB.safe_str(row['ally_name'])
            r['ally_tag'] = GalaxyDB.safe_str(row['ally_tag'])
            r['ally_members'] = GalaxyDB.safe_int(row['ally_members'])
            # process ally info
            if r['ally_tag'] != r['ally_name']:
                r['ally_name'] += ' [{0}]'.format(r['ally_tag'])
            r['ally_name'] += ' ({0} тел)'.format(r['ally_members'])
            if r['ally_members'] == 0:
                r['ally_name'] = ''
            r['luna_name'] = GalaxyDB.safe_str(row['luna_name'])
            r['luna_diameter'] = GalaxyDB.safe_int(row['luna_diameter'])
            # process luna
            if (r['luna_name'] != '') and (r['luna_diameter'] > 0):
                r['luna_name'] += ' ({0})'.format(r['luna_diameter'])
            # process planet type (detect bases)
            if r['planet_type'] == GalaxyDB.PLANET_TYPE_BASE:
                r['planet_name'] += ' (base)'
            rows_list.append(r)
        res_dict = dict()
        res_dict['rows'] = rows_list
        return res_dict

    def query_like(self, col_name, value, sort_col=None, sort_order=None):
        if type(col_name) == str:
            where = 'WHERE ' + col_name + ' LIKE ?'
            params = (value, )
        elif type(col_name) == list:
            where = 'WHERE'
            params = list()
            for col in col_name:
                where += ' '
                where += col
                where += ' LIKE ? OR'
                params.append(value)
            where = where[0:-2]
        else:
            where = None
            params = None
        q = self.create_query(where, sort_col, sort_order)
        self._cur.execute(q, params)
        return self._rows_to_res_list()

    def query_inactives(self, user_flags, gals, s_min, s_max, min_rank=0, sort_col=None, sort_order=None):
        user_where = ''
        gals_where = ''
        syss_where = ''
        rank_where = ''
        # user flags
        # user online time
        user_ot = ''
        if 'i' in user_flags:
            user_ot = 'user_onlinetime=1'
        if 'I' in user_flags:
            user_ot = 'user_onlinetime>0'
        user_where += user_ot
        # user banned or not banned, exlusively set
        if 'G' in user_flags:
            if user_where != '':
                user_where += ' AND '
            user_where += 'user_banned>0'
        else:
            if user_where != '':
                user_where += ' AND '
            user_where += 'user_banned=0'
        # user ro or not, exclusively
        if 'U' in user_flags:
            if user_where != '':
                user_where += ' AND '
            user_where += 'user_ro>0'
        else:
            if user_where != '':
                user_where += ' AND '
            user_where += 'user_ro=0'
        # galaxies
        if type(gals) == list:
            gals_where = 'g IN ('
            for g in gal_ints:
                gals_where += '{0},'.format(g)
            gals_where = gals_where[0:-1]
            gals_where += ')'
        # systems
        if s_min <= s_max:
            syss_where = 's BETWEEN {0} AND {1}'.format(s_min, s_max)
        # rank
        if min_rank > 0:
            rank_where = ' AND (user_rank BETWEEN 1 AND {0})'.format(min_rank)
        # final WHERE clause
        where = 'WHERE ({0}) AND ({1}) AND ({2}) {3}'.format(user_where, gals_where, syss_where, rank_where)
        q = self.create_query(where, sort_col, sort_order)
        self._cur.execute(q)
        return self._rows_to_res_list()

    def query_planets_count(self, gal: int, sys_: int) -> int:
        self._cur.execute('SELECT COUNT(*) FROM planets WHERE g=? AND s=?', (gal, sys_))
        rows = self._cur.fetchall()
        assert len(rows) == 1
        assert len(rows[0]) == 1
        return self.safe_int(rows[0][0])


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
