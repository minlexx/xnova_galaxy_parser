# -*- coding: utf-8 -*-
import sqlite3


class GalaxyDB:

    PLANET_TYPE_PLANET = 1
    PLANET_TYPE_BASE = 5

    def __init__(self):
        self._conn = sqlite3.connect('galaxy5.db')
        self._conn.row_factory = sqlite3.Row
        self._cur = self._conn.cursor()
        self._log_queries = False

    def close(self):
        self._cur.close()
        self._conn.close()
        del self._cur
        del self._conn

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

    def query_inactives(self, user_flags, gal_ints, s_min, s_max, min_rank=0, sort_col=None, sort_order=None):
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
        if type(gal_ints) == list:
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

    def find_player_by_name(self, player_name: str) -> tuple:
        q = 'SELECT user_id, user_name FROM planets WHERE user_name LIKE ? LIMIT 1'
        self._cur.execute(q, (player_name, ))
        rows = self._cur.fetchall()
        if len(rows) == 1:
            return rows[0]
        return None

    def query_player_planets(self, player_name: str) -> list:
        q = 'SELECT g,s,p, planet_name, planet_type, luna_name, luna_diameter \n' \
            ' FROM planets WHERE user_name=?'
        self._cur.execute(q, (player_name,))
        ret = []
        for row in self._cur.fetchall():
            p = dict()
            p['g'] = GalaxyDB.safe_int(row['g'])
            p['s'] = GalaxyDB.safe_int(row['s'])
            p['p'] = GalaxyDB.safe_int(row['p'])
            p['planet_name'] = GalaxyDB.safe_str(row['planet_name'])
            p['planet_type'] = GalaxyDB.safe_int(row['planet_type'])
            p['luna_name'] = GalaxyDB.safe_str(row['luna_name'])
            p['luna_diameter'] = GalaxyDB.safe_int(row['luna_diameter'])
            ret.append(p)
        return ret
