import sys
import re
import argparse
import logging
import time
import html.parser

import requests
import requesocks

from xnova import xn_logger
from xnova.xn_auth import xnova_authorize
from xnova.xn_page_dnl import XNovaPageDownload
from xnova.xn_parser import XNParserBase, get_attribute, get_tag_classes

from xnova.lastlogs_utils import safe_int, LLDb


logger = xn_logger.get(__name__, debug=True)


def split_attacker_defender_line(s: str) -> tuple:
    # Атакующий Шахтерская лопятка [1:2:3]
    # Защитник Злой фермер [1:2:5]
    if s.startswith('Атакующий'):
        s = s[10:]
    if s.startswith('Защитник'):
        s = s[9:]
    bpos = s.find('[')
    if bpos == -1:
        return s
    name = s[0:bpos-1]
    coords = s[bpos:]
    return name, coords


class PageParser(XNParserBase):  # parent of XNParserBase is html.parser.HTMLParser
    def __init__(self):
        super(PageParser, self).__init__()
        # reset code
        self.is_nonexistent_log = True
        self.log_time = ''
        self.attacker = ''
        self.defender = ''
        #
        self._in_report_user = False
        self._in_report_fleet = False
        self._attackers_coords_dict = {}
        self._attackers_coords_dict = {}

    def reset(self):
        super(PageParser, self).reset()
        self.is_nonexistent_log = True
        self.log_time = ''
        self.attacker = ''
        self.defender = ''
        #
        self._in_report_user = False
        self._in_report_fleet = False
        self._attackers_coords_dict = {}
        self._defender_coords_dict = {}

    def handle_starttag(self, tag, attrs):
        super(PageParser, self).handle_starttag(tag, attrs)
        if tag == 'table':
            tbl_classes = get_tag_classes(attrs)
            if (tbl_classes is not None) and ('report_user' in tbl_classes):
                self._in_report_user = True
                return
        if tag == 'div':
            div_classes = get_tag_classes(attrs)
            if (div_classes is not None) and ('report_fleet' in div_classes):
                self._in_report_fleet = True

    # @override XNParserBase.handle_data2()
    def handle_data2(self, data: str, tag: str, attrs: list):
        if tag == 'title':
            logger.debug('Found title: [{0}]'.format(data))
            # <title>Боевой доклад :: Звездная Империя 5</title> - success, we have log
            # <title>Сообщение :: Звездная Империя 5</title> - fail, nonexistent log id
            # also nonexistent log has:
            # <th class="errormessage">Запрашиваемого лога не существует в базе данных</th>
            if data.startswith('Боевой доклад'):
                self.is_nonexistent_log = False
            return
        if tag == 'div':
            div_classes = get_tag_classes(attrs)
            if (div_classes is not None) and ('report' in div_classes):
                logger.debug(' Found <div class=report>, data = [{0}]'.format(data))
                # data = "В 19-06-2016 10:03:01 произошёл бой между следующими флотами:"
                self.log_time = data[2:21]
                logger.debug('  got log_time = [{0}]'.format(self.log_time))
                return
        if tag == 'span':
            span_classes = get_tag_classes(attrs)
            span_negative = 'negative' in span_classes
            span_positive = 'positive' in span_classes
            if self._in_report_user and span_negative:
                if self.attacker != '':
                    self.attacker += ','
                self.attacker += data
                self._in_report_user = False
            if self._in_report_user and span_positive:
                self._in_report_user = False
                if self.defender != '':
                    self.defender += ','
                self.defender += data
            # <div class='report_fleet'><span class='negative'>Атакующий xXxHari6aTop3000xXx [1:5:3]</span>
            if self._in_report_fleet and span_negative:
                # Атакующий Шахтерская лопятка [1:2:3]
                name, coords = split_attacker_defender_line(data)
                self._in_report_fleet = False
                if name not in self._attackers_coords_dict:
                    self._attackers_coords_dict[name] = coords
            if self._in_report_fleet and span_positive:
                name, coords = split_attacker_defender_line(data)
                self._in_report_fleet = False
                if name not in self._defender_coords_dict:
                    self._defender_coords_dict[name] = coords
            return


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

    if (ap_result.login == '') or (ap_result.password == ''):
        logger.critical('You MUST provide login and password!')
        exit(1)

    lldb = LLDb(ap_result.dbfile)
    page_dnl = XNovaPageDownload()
    page_dnl.xnova_url = 'uni5.xnova.su'

    cookies_dict = xnova_authorize(page_dnl.xnova_url, ap_result.login, ap_result.password)
    if cookies_dict is None:
        logger.error('XNova authorization failed!')
        exit(1)

    page_dnl.set_cookies_from_dict(cookies_dict, do_save=False)

    lastlog_id = lldb.get_lastlog_id()
    logger.debug('Got lastlog ID from DB: {0}'.format(lastlog_id))
    if lastlog_id == 0:
        lastlog_id += 1

    parser = PageParser()

    num_errors = 0
    max_errors = 20
    num_loops = 0
    failed_logids = []
    log_id = lastlog_id
    while True:
        num_loops += 1
        page_dnl.set_referer('https://uni5.xnova.su/log/')
        url = 'log/{0}/'.format(log_id)
        logger.debug('Downloading {0}...'.format(url))
        page_content = page_dnl.download_url_path(url, return_binary=False)
        if page_content is None:
            num_errors += 1
            failed_logids.append(log_id)
            logger.error('Failed to download log page!')
        else:
            # parse page content
            parser.parse_page_content(page_content)
            if parser.is_nonexistent_log:
                num_errors += 1
                failed_logids.append(log_id)
            # success, this is battle log
            parser.log_id = log_id
            #
            logger.debug(' Attackers: {0}'.format(parser.attacker))
            logger.debug(' Defenders: {0}'.format(parser.defender))

        log_id += 1

        if num_errors >= max_errors:
            logger.info('Max errors ({0}) exceeded, exiting'.format(num_errors))
            logstr = ''
            for flid in failed_logids:
                logstr += '{0},'.format(flid)
            logstr = logstr[:-1]
            logger.info('Failed log IDs: {0}'.format(logstr))
            break
        if num_loops >= 1:
            break

    exit(0)


if __name__ == '__main__':
    main()
    sys.exit(0)
