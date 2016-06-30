#!/usr/bin/python3
# -*- coding: utf-8 -*-
import sys
import os
import time
import configparser
import logging
import sqlite3
import re
import html.parser

import requests
import requests.exceptions

from xnova.lastlogs_utils import safe_int, LLDb


# general config parameters
XNOVA_URL = 'uni4.xnova.su'
LASTLOG_ID = 14600
LASTLOG_DB = 'lastlogs.db'


def logger_init(name, debug=False, use_stderr=False):
    level = logging.INFO
    if debug:
        level = logging.DEBUG
    # can have loggers with different names
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    # each module logger has its own handler attached
    if use_stderr:
        log_handler = logging.StreamHandler(stream=sys.stderr)
    else:
        log_handler = logging.StreamHandler(stream=sys.stdout)
    log_handler.setLevel(level)
    log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    log_handler.setFormatter(log_formatter)
    logger.addHandler(log_handler)
    return logger


logger = logger_init(__name__, debug=True, use_stderr=True)


def config_read():
    global XNOVA_URL, LASTLOG_ID, LASTLOG_DB
    cfg = configparser.ConfigParser()
    cfg.read('config/net.ini', encoding='UTF-8')
    if 'net' in cfg:
        XNOVA_URL = cfg['net']['xnova_url']
        logger.debug('cfg: XNOVA_URL: {0}'.format(XNOVA_URL))
    if 'lastlog' in cfg:
        LASTLOG_ID = safe_int(cfg['lastlog']['lastlog_id'])
        LASTLOG_DB = cfg['lastlog']['lastlog_db']
        logger.debug('cfg: LASTLOG_ID: {0}'.format(LASTLOG_ID))
        logger.debug('cfg: LASTLOG_DB: {0}'.format(LASTLOG_DB))


class PageDownloader:
    def __init__(self):
        self.xnova_url = XNOVA_URL
        self.user_agent = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.sess = requests.Session()
        self.sess.headers.update({'user-agent': self.user_agent})
        self.sess.headers.update({'referer': 'http://{0}/'.format(self.xnova_url)})

    def download_url(self, url: str, return_binary=False):
        ret_html = ''
        logger.debug('Downloading url = [{0}]'.format(url))
        try:
            r = self.sess.get(url)
            if r.status_code == requests.codes.ok:
                if not return_binary:
                    ret_html = r.text
                else:
                    ret_html = r.content
            else:
                logger.error('Unexpected response code: HTTP {0}'.format(r.status_code))
        except requests.exceptions.RequestException as e:
            logger.error('Exception {0}'.format(type(e)))
        return ret_html

    def download_log_html(self, log_id, return_binary=False):
        url = 'http://' + self.xnova_url + '/?set=log&id=' + str(log_id)
        return self.download_url(url)


class PageParser(html.parser.HTMLParser):
    def __init__(self):
        super(PageParser, self).__init__(convert_charrefs=True)
        self.reset()

    def reset(self):
        super(PageParser, self).reset()
        # public
        self.is_nonexistent_log = True
        self.log_has_title = False
        #
        self.log_id = 0
        self.log_time = 0
        self.attacker = ''
        self.defender = ''
        self.attacker_coords = ''
        self.defender_coords = ''
        self.total_loss = 0
        self.po_me = 0
        self.po_cry = 0
        self.win_me = 0
        self.win_cry = 0
        self.win_deit = 0
        # private
        self._tag = ''
        self._attrs = []

    def parse(self, logid: int, s: str):
        self.reset()
        self.log_id = logid
        self.feed(s)

    def handle_starttag(self, tag, attrs):
        super(PageParser, self).handle_starttag(tag, attrs)
        self._tag = tag
        self._attrs = attrs

    def handle_endtag(self, tag):
        super(PageParser, self).handle_endtag(tag)
        self._tag = ''
        self._attrs = []

    def handle_data(self, data: str):
        super(PageParser, self).handle_data(data)
        data = data.strip()
        if data == '':
            return
        # logger.debug('handle_data: data={0} tag={1} attrs={2}'.format(data, self._tag, self._attrs))
        if self._tag == 'title':
            # logger.debug('Found title: [{0}]'.format(data))
            # check that log has all the info in title
            if data.find(' vs ') == -1:  # no " vs " substring
                return
            if data.find('(П:') == -1:  # no losses information substring
                return
            # only set has_title if all info found
            self.log_has_title = True
            # ScumWir vs Сергей Такачёв (П: 1.471.000)
            # Artik,kizzek,Uragan,Cupuyc,minlexx,Athl,ScumWir vs GART1610 (П: 1.601kk)
            parts = data.split(' vs ', 2)
            self.attacker = parts[0].strip()
            parts = parts[1].split('(П:', 2)
            self.defender = parts[0].strip()
            total_loss_str = parts[1].strip()
            total_loss_str = total_loss_str.replace('.', '')
            total_loss_str = total_loss_str.replace(')', '')
            self.total_loss = safe_int(total_loss_str)
            logger.info('log #{0}: Battle [{1}] vs [{2}] (loss: {3})'.format(
                self.log_id, self.attacker, self.defender, self.total_loss))
            return
        if self._tag == 'center':
            # [В 30-11-2015 03:25:26 произошёл бой между следующими флотами:]
            if data.endswith('произошёл бой между следующими флотами:'):
                btime = data[2:21]
                stt = time.strptime(btime, '%d-%m-%Y %H:%M:%S')
                self.log_time = int(time.mktime(stt))
                logger.debug('    log time: [{0} = {1}]'.format(btime, self.log_time))
                # if we got a battle time, the log exists
                self.is_nonexistent_log = False
                return
            if data == 'Данный лог боя пока недоступен для просмотра!':
                self.is_nonexistent_log = True
                logger.debug('    log {0} marked as non-existent (1)'.format(self.log_id))
                return
            if data == 'Запрашиваемого лога не существует в базе данных':
                self.is_nonexistent_log = True
                logger.debug('    log {0} marked as non-existent (2)'.format(self.log_id))
                return
        if self._tag == 'span':
            # Атакующий ScumWir [1:233:9]
            # Защитник Сергей Такачёв [1:211:7]
            att_line = 'Атакующий ' + self.attacker + ' ['
            def_line = 'Защитник ' + self.defender + ' ['
            # Found att coords: [Атакующий ScumWir [1:233:9]]
            if (data.find(att_line) != -1) and (self.attacker_coords == ''):
                m = re.search(r'\[(\d+):(\d+):(\d+)\]', data)
                if m is not None:
                    self.attacker_coords = m.group(0)
                    logger.debug('    att coords = {0}'.format(self.attacker_coords))
                return
            if (data.find(def_line) != -1) and (self.defender_coords == ''):
                m = re.search(r'\[(\d+):(\d+):(\d+)\]', data)
                if m is not None:
                    self.defender_coords = m.group(0)
                    logger.debug('    def coords = {0}'.format(self.attacker_coords))
                return
        if self._tag == 'br':
            m = re.search(r'Он получает (\d+) металла, (\d+) кристалла и (\d+) дейтерия', data)
            if m is not None:
                logger.info('Match: [{0}]'.format(m.group(0)))
                return
        if self._tag == 'td':
            m = re.search(r'Поле обломков: ([\d\.]+) металла и ([\d\.]+) кристалла', data)
            if m is not None:
                self.po_me = safe_int(m.group(1))
                self.po_cry = safe_int(m.group(2))
                logger.debug('    PO: {0}m / {1}c'.format(self.po_me, self.po_cry))
                return
            return
        # logger.debug('{0}: data = {1}'.format(self._tag, data))
        m = re.search(r'Он получает ([\d\.]+) металла, ([\d\.]+) кристалла и ([\d\.]+) дейтерия', data)
        if m is not None:
            self.win_me = safe_int(m.group(1))
            self.win_cry = safe_int(m.group(2))
            self.win_deit = safe_int(m.group(3))
            logger.debug('    win: {0}m / {1}c / {2}d'.format(self.win_me, self.win_cry, self.win_deit))
            return


def main():
    # load config
    config_read()

    # calculate starting log ID
    llid = LASTLOG_ID
    db = LLDb(LASTLOG_DB)
    db_llid = db.get_lastlog_id()
    if db_llid > llid:
        llid = db_llid
    llid += 1

    exitcode = 0
    new_logs_added = 0
    num_failures = 0
    max_failures = 10

    # logging
    logger.info('using {0} as last log id'.format(llid))
    logger.info('current directory: {0}'.format(os.getcwd()))

    # go into the loop
    pd = PageDownloader()
    pp = PageParser()
    while True:
        html_text = pd.download_log_html(llid)
        pp.parse(llid, html_text)
        if not pp.log_has_title:
            num_failures += 1
            if num_failures >= max_failures:
                logger.warn('{0} of {1} max failures, ending loop'.format(num_failures, max_failures))
                exitcode = 1
                break
        if (pp.log_has_title) and (not pp.is_nonexistent_log):
            db.store_log(pp)
            new_logs_added += 1
        llid += 1  # move and try next log ID

    logger.info('{0} total new logs were added to database.'.format(new_logs_added))
    logger.info('{0}/{1} failures happened.'.format(num_failures, max_failures))
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
