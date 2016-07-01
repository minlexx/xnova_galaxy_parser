#!/usr/bin/python3
# -*- coding: utf-8 -*-
import sys
import re
import argparse
import logging
import time

from xnova import xn_logger
from xnova.xn_auth import xnova_authorize
from xnova.xn_page_dnl import XNovaPageDownload
from xnova.xn_parser import XNParserBase, get_tag_classes

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


class ParseError(RuntimeError):
    def __init__(self, msg: str):
        self.message = str


class PageParser(XNParserBase):  # parent of XNParserBase is html.parser.HTMLParser
    def __init__(self):
        super(PageParser, self).__init__()
        # reset code
        self.is_nonexistent_log = True
        self.log_time = 0
        self.log_time_str = ''
        self.attacker = ''
        self.defender = ''
        self.attacker_coords = ''
        self.defender_coords = ''
        self.total_loss = 0
        self.att_loss = 0
        self.def_loss = 0
        self.po_me = 0
        self.po_cry = 0
        self.win_me = 0
        self.win_cry = 0
        self.win_deit = 0
        self.moon_chance = 0
        #
        self._in_report_user = False
        self._in_report_fleet = False
        self._in_report_result = False
        self._attackers_list = []
        self._defenders_list = []
        self._attackers_coords_dict = {}
        self._defender_coords_dict = {}

    def reset(self):
        super(PageParser, self).reset()
        self.is_nonexistent_log = True
        self.log_time = 0
        self.log_time_str = ''
        self.attacker = ''
        self.defender = ''
        self.attacker_coords = ''
        self.defender_coords = ''
        self.total_loss = 0
        self.att_loss = 0
        self.def_loss = 0
        self.po_me = 0
        self.po_cry = 0
        self.win_me = 0
        self.win_cry = 0
        self.win_deit = 0
        self.moon_chance = 0
        #
        self._in_report_user = False
        self._in_report_fleet = False
        self._in_report_result = False
        self._attackers_list = []
        self._defenders_list = []
        self._attackers_coords_dict = {}
        self._defender_coords_dict = {}

    def handle_starttag(self, tag, attrs):
        super(PageParser, self).handle_starttag(tag, attrs)
        if tag == 'table':
            tbl_classes = get_tag_classes(attrs)
            if (tbl_classes is not None) and ('report_user' in tbl_classes):
                self._in_report_user = True
                return
            if (tbl_classes is not None) and ('report_result' in tbl_classes):
                self._in_report_result = True
                return
        if tag == 'div':
            div_classes = get_tag_classes(attrs)
            if (div_classes is not None) and ('report_fleet' in div_classes):
                self._in_report_fleet = True

    def handle_endtag(self, tag: str):
        super(PageParser, self).handle_endtag(tag)
        # post-processing
        if tag == 'html':
            for att in self._attackers_list:
                try:
                    self.attacker_coords += self._attackers_coords_dict[att] + ','
                except KeyError:
                    logger.error('Cannot find [{0}] in attacker coords dict, attackers list:')
                    logger.error('{0}'.format(str(self._attackers_list)))
            for defender in self._defenders_list:
                try:
                    self.defender_coords += self._defender_coords_dict[defender] + ','
                except KeyError:
                    logger.error('Cannot find [{0}] in defender coords dict, defenders list:')
                    logger.error('{0}'.format(str(self._defenders_list)))
            self.attacker_coords = self.attacker_coords[:-1]
            self.defender_coords = self.defender_coords[:-1]

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
                self.log_time_str = data[2:21]
                stt = time.strptime(self.log_time_str, '%d-%m-%Y %H:%M:%S')
                self.log_time = int(time.mktime(stt))
                logger.debug('  got log_time_str = "{0}", as time_t: {1}'.format(
                    self.log_time_str, self.log_time))
                return
        if tag == 'span':
            span_classes = get_tag_classes(attrs)
            span_negative = 'negative' in span_classes
            span_positive = 'positive' in span_classes
            if self._in_report_user and span_negative:
                if self.attacker != '':
                    self.attacker += ','
                self.attacker += data
                self._attackers_list.append(data)
                self._in_report_user = False
            if self._in_report_user and span_positive:
                if self.defender != '':
                    self.defender += ','
                self._defenders_list.append(data)
                self.defender += data
                self._in_report_user = False
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
        if self._in_report_result:
            # DEBUG __main__ Атакующий выиграл битву!
            # DEBUG __main__ Он получает 13.231 металла, 6.438 кристалла и 1.900 дейтерия
            # DEBUG __main__ Атакующий потерял 0 единиц.
            # DEBUG __main__ Обороняющийся потерял 8.000 единиц.
            # DEBUG __main__ Поле обломков: 600 металла и 600 кристалла.
            # DEBUG __main__ Шанс появления луны составляет 0%
            if data.startswith('Он получает'):
                m = re.search(r'([\d\.]+) металла, ([\d\.]+) кристалла и ([\d\.]+) дейтерия', data)
                if m is None:
                    raise ParseError('Failed to parse win resources str: [{0}]'.format(data))
                self.win_me = safe_int(m.group(1))
                self.win_cry = safe_int(m.group(2))
                self.win_deit = safe_int(m.group(3))
            elif data.startswith('Атакующий потерял'):
                m = re.search(r'потерял ([\d\.]+) единиц', data)
                if m is None:
                    raise ParseError('Failed to parse attacker loss str: [{0}]'.format(data))
                self.att_loss = safe_int(m.group(1))
                self.total_loss += self.att_loss
            elif data.startswith('Обороняющийся потерял'):
                m = re.search(r'потерял ([\d\.]+) единиц', data)
                if m is None:
                    raise ParseError('Failed to parse defender loss str: [{0}]'.format(data))
                self.def_loss = safe_int(m.group(1))
                self.total_loss += self.def_loss
            elif data.startswith('Поле обломков:'):
                m = re.search(r'([\d\.]+) металла и ([\d\.]+) кристалла', data)
                if m is None:
                    raise ParseError('Failed to parse debris field: [{0}]'.format(data))
                self.po_me = safe_int(m.group(1))
                self.po_cry = safe_int(m.group(2))
            elif data.startswith('Шанс появления луны составляет '):
                # "Шанс появления луны составляет 0%"
                self.moon_chance = safe_int(data[31:-1])
                logger.debug('   moon chance: {0}%'.format(self.moon_chance))
            return


def main():
    # parse command line
    ap = argparse.ArgumentParser(description='XNova Uni5 combat logs parser.')
    ap.add_argument('--version', action='version', version='%(prog)s 0.2')
    ap.add_argument('--debug', action='store_true', help='Enable debug logging.')
    ap.add_argument('--login', nargs='?', default='', type=str, metavar='LOGIN',
                    help='Login to use to authorize in XNova game')
    ap.add_argument('--password', nargs='?', default='', type=str, metavar='PASS',
                    help='Password to use to authorize in XNova game')
    ap.add_argument('--dbfile', nargs='?', default='lastlogs5.db', type=str, metavar='DBFILE',
                    help='Name of sqlite3 db file to store logs data. Default is "lastlogs5.db"')
    ap.add_argument('--delay', nargs='?', default=5.0, type=float, metavar='SECONDS',
                    help='Delay in seconds between requests (default: 5 secs)')
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
    lastlog_id += 1  # move on to next log id

    parser = PageParser()

    num_errors = 0
    max_errors = 20
    num_logs_parsed = 0
    failed_logids = []
    nonexistent_logids = []
    log_id = lastlog_id
    while True:
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
            try:
                parser.reset()  # reset manually before next parse, clean prev. data
                parser.parse_page_content(page_content)
                if parser.is_nonexistent_log:
                    num_errors += 1
                    nonexistent_logids.append(log_id)
                else:
                    # success, this is battle log
                    parser.log_id = log_id
                    lldb.store_log(parser)
                    num_logs_parsed += 1
                    num_errors = 0  # reset number of errors on successful parse
                    #
                    logger.debug('Battle at {0}: {1} vs {2}'.format(
                        parser.log_time_str, parser.attacker, parser.defender))
                    logger.debug(' Coords: {0} vs {1}'.format(parser.attacker_coords, parser.defender_coords))
                    logger.debug(' Losses: att: {0}, def: {1}, total: {2}'.format(
                        parser.att_loss, parser.def_loss, parser.total_loss))
                    logger.debug(' Field: {0} me, {1} cry'.format(parser.po_me, parser.po_cry))
                    logger.debug(' Win res: {0} me, {1} cry, {2} deit'.format(
                        parser.win_me, parser.win_cry, parser.win_deit))
            except ParseError as ve:
                num_errors += 1
                failed_logids.append(log_id)
                logger.error('Failed to parse log id {0} !'.format(log_id))
                logger.error('Error message: {0}'.format(ve.message))

        log_id += 1

        if num_errors >= max_errors:
            logger.info('Max errors ({0}) exceeded, exiting'.format(num_errors))
            break

        time.sleep(ap_result.delay)

    # Output statistics
    # always output failed logs
    logstr = ''
    for flid in failed_logids:
        logstr += '{0},'.format(flid)
    if logstr != '':
        logstr = logstr[:-1]
        logger.info('STATS: Failed logs: {0}'.format(logstr))
    # output nonexistent logs
    logstr = ''
    for flid in nonexistent_logids:
        logstr += '{0},'.format(flid)
    if logstr != '':
        logstr = logstr[:-1]
        logger.info('STATS: Non-existent logs: {0}'.format(logstr))
    logger.info('STATS: Succesfully parsed: {0} logs'.format(num_logs_parsed))

    exit(0)


if __name__ == '__main__':
    main()
    sys.exit(0)
