import sqlite3
from . import xn_logger


logger = xn_logger.get(__name__, debug=False)


def safe_int(v: str) -> int:
    ret = 0
    multiplier = 1
    if v is None:
        return 0
    # check for dotted-number (1.123.567)
    if isinstance(v, str):
        if v.find('.') >= 0:
            v = v.replace('.', '')
        # it may be this string: (1.601kk)
        if v.endswith('kk'):
            v = v[:-2]
            multiplier = 1000000
    try:
        ret = int(v)
    except ValueError:
        ret = 0
    return ret * multiplier


class LLDb:
    def __init__(self, db_fn: str):
        self._conn = sqlite3.connect(db_fn)
        self.check_tables()

    def check_tables(self):
        q = 'CREATE TABLE IF NOT EXISTS logs ( ' \
            ' log_id INT, ' \
            ' log_time TEXT, ' \
            ' attacker TEXT, ' \
            ' defender TEXT, ' \
            ' attacker_coords TEXT, ' \
            ' defender_coords TEXT, ' \
            ' total_loss INT, ' \
            ' po_me INT, ' \
            ' po_cry INT,' \
            ' win_me INT, ' \
            ' win_cry INT, ' \
            ' win_deit INT )'
        cur = self._conn.cursor()
        cur.execute(q)
        self._conn.commit()
        cur.close()

    def get_lastlog_id(self) -> int:
        q = 'SELECT MAX(log_id) FROM logs'
        cur = self._conn.cursor()
        cur.execute(q)
        rows = cur.fetchall()
        cur.close()
        if rows is None:
            return 0
        for row in rows:
            return safe_int(row[0])
        return 0

    def log_exists(self, log_id: int):
        q = 'SELECT COUNT(*) FROM logs WHERE log_id=?'
        cur = self._conn.cursor()
        cur.execute(q, (log_id, ))
        rows = cur.fetchall()
        cur.close()
        for row in rows:
            cnt = safe_int(row[0])
            if cnt > 0:
                return True
            return False

    def store_log(self, o):
        if self.log_exists(o.log_id):
            logger.warn('Refusing to add duplicate log id: {0}'.format(o.log_id))
            return
        #
        q = 'INSERT INTO logs (log_id, log_time, attacker, defender, ' \
            ' attacker_coords, defender_coords, total_loss, ' \
            ' po_me, po_cry, win_me, win_cry, win_deit) ' \
            'VALUES (?,?, ?,?, ?,?, ?, ?,?, ?,?,?)'
        cur = self._conn.cursor()
        cur.execute(q, (o.log_id, o.log_time, o.attacker, o.defender,
                        o.attacker_coords, o.defender_coords, o.total_loss,
                        o.po_me, o.po_cry, o.win_me, o.win_cry, o.win_deit))
        self._conn.commit()
        cur.close()
        logger.info('Saved log id: {0}'.format(o.log_id))
