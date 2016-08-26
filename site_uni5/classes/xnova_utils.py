# -*- coding: utf-8 -*-
import sys
from html.parser import HTMLParser

import requests
import requests.exceptions
import requests.cookies

import execjs
import execjs._exceptions as execjs_exceptions


def xnova_authorize(xn_host, xn_login, xn_password) -> dict:
    postdata = {
        'emails': xn_login,
        'password': xn_password,
        'rememberme': 'on'
    }

    post_url = 'http://uni4.xnova.su/?set=login&xd'

    # uni5 fix
    if xn_host.startswith('uni5'):
        postdata = {
            'email': xn_login,
            'password': xn_password,
            'rememberme': 'on',
            'ajax': 'Y'
        }
        post_url = 'https://uni5.xnova.su/login/?'

    r = requests.post(post_url, data=postdata, allow_redirects=False)
    # print(r.content)  # empty
    # print('----------------------------')
    # print(r.text)     # also empty
    cookies_dict = {}
    for single_cookie in r.cookies.iteritems():
        cookies_dict[single_cookie[0]] = single_cookie[1]
    # print('cookies_dict will be:')
    # print(cookies_dict)
    if ('x_id' not in cookies_dict) or ('x_secret' not in cookies_dict) \
            or ('x_uni' not in cookies_dict):
        # uni4 auth failed, try uni5
        if xn_host.startswith('uni5'):
            if ('PHPSESSID' not in cookies_dict) or ('session_id' not in cookies_dict):
                return None
    return cookies_dict


# Incapsulates network layer:
# all operations for getting data from server
class PageDownloader:
    def __init__(self, cookies_dict: dict=None):
        self.xnova_url = 'uni5.xnova.su'
        self.user_agent = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:48.0) Gecko/20100101 Firefox/48.0'
        self.error_str = None
        self.proxy = None
        # construct requests HTTP session
        self.sess = requests.Session()  # else normal session
        self.sess.headers.update({'user-agent': self.user_agent})
        self.sess.headers.update({'referer': 'https://{0}/'.format(self.xnova_url)})
        if cookies_dict:
            self.set_cookies_from_dict(cookies_dict)

    def set_useragent(self, ua_str: str):
        self.user_agent = ua_str
        self.sess.headers.update({'user-agent': self.user_agent})

    def set_referer(self, ref_str: str):
        self.sess.headers.update({'referer': ref_str})

    def set_cookies_from_dict(self, cookies_dict: dict):
        self.sess.cookies = requests.cookies.cookiejar_from_dict(cookies_dict)

    # error handler
    def _set_error(self, errstr):
        self.error_str = errstr

    # real downloader function
    # returns None on failure
    def download_url_path(self, url_path: str, return_binary=False):
        self.error_str = None  # clear error
        # construct url to download
        url = 'http://{0}/{1}'.format(self.xnova_url, url_path)
        ret = None
        try:
            r = self.sess.get(url)
            if r.status_code == requests.codes.ok:
                if not return_binary:
                    ret = r.text
                else:
                    ret = r.content
                # on successful request, update referer header for the next request
                self.sess.headers.update({'referer': url})
            else:
                self._set_error('HTTP {0}'.format(r.status_code))
        except requests.exceptions.RequestException as e:
            self._set_error(str(e))
        return ret


# converts string to int, silently ignoring errors
def safe_int(data: str):
    ret = 0
    if data == '-':  # indicates as "None", return 0
        return ret
    try:
        ret = int(data.replace('.', ''))
    except ValueError:
        ret = 0
    return ret


# get attribute value from tag attributes
def get_attribute(attrs: list, attr_name: str) -> str:
    """
    Gets attribute value from tag attributes, or None if not found
    :param attrs: attributes list as get from http_parser.handle_starttag()
    :param attr_name: attribute to search for
    :return: given attribute value (str), or None if not found
    """
    if attrs is None:
        return None
    # attrs: list of tuples: [(attr_name1, attr_value2), (), ... ]
    for attr_tuple in attrs:
        if attr_tuple[0] == attr_name:
            return attr_tuple[1]
    return None


def get_tag_classes(attrs: list) -> list:
    """
    Get tag class as list of strings, or None if not set
    :param attrs: attrs list, from handle_starttag()
    :return: strings list, classes if found or None
    """
    a_class = get_attribute(attrs, 'class')
    if a_class is None:
        return None
    cls_list = a_class.split(' ')
    return cls_list


# extends html.parser.HTMLParser class
# by remembering tags path
class XNParserBase(HTMLParser):
    def __init__(self):
        if (sys.version_info.major >= 3) and (sys.version_info.minor >= 5):
            # python 3.5 does not know the keyword "strict" in constructor
            super(XNParserBase, self).__init__(convert_charrefs=True)
        else:
            super(XNParserBase, self).__init__(strict=False, convert_charrefs=True)
        self._last_tag = ''
        self._last_attrs = list()

    def handle_starttag(self, tag: str, attrs: list):
        super(XNParserBase, self).handle_starttag(tag, attrs)
        self._last_tag = tag
        self._last_attrs = attrs

    def handle_endtag(self, tag: str):
        super(XNParserBase, self).handle_endtag(tag)
        self._last_tag = ''
        self._last_attrs = list()

    def handle_data(self, data: str):
        super(XNParserBase, self).handle_data(data)
        data_s = data.strip()
        if len(data_s) < 1:
            return
        self.handle_data2(data_s, self._last_tag, self._last_attrs)

    def handle_data2(self, data: str, tag: str, attrs: list):
        pass

    def parse_page_content(self, page: str):
        if page is not None:
            self.feed(page)


class XNGalaxyParser(XNParserBase):
    def __init__(self):
        super(XNGalaxyParser, self).__init__()
        self._in_galaxy = False
        self.script_body = ''
        self.galaxy_rows = []
        self.error_str = ''

    def clear(self):
        self.script_body = ''
        self.galaxy_rows = []
        self.error_str = ''

    def handle_starttag(self, tag: str, attrs: list):
        super(XNGalaxyParser, self).handle_starttag(tag, attrs)
        if tag == 'div':
            # find [<div id='galaxy'>]
            div_id = get_attribute(attrs, 'id')
            if div_id is not None:
                if div_id == 'galaxy':
                    self._in_galaxy = True

    def handle_endtag(self, tag: str):
        super(XNGalaxyParser, self).handle_endtag(tag)
        if self._in_galaxy and tag == 'script':
            self._in_galaxy = False

    def handle_data2(self, data: str, tag: str, attrs: list):
        if self._in_galaxy and (tag == 'script'):
            self.script_body = data
            # logger.debug('Got galaxy script: [{0}]'.format(self.script_body))
        return  # def handle_data()

    def unscramble_galaxy_script(self):
        # check script body
        if not self.script_body.startswith('var Deuterium = '):
            self.error_str = 'Invalid format of script body: cannot parse it!'
            return None

        # create JavaScript interpreter runtime
        try:
            js_runtime = execjs.get('Node')
        except execjs_exceptions.RuntimeUnavailableError:
            js_runtime = execjs.get()  # default

        # find galaxy script part
        eval_start = self.script_body.find('eval(function(p,a,c,k,e,d)')
        if eval_start == -1:
            # try to find an end of galaxy rows declaration; maybe it is not packed (uni5)
            eval_end = self.script_body.find("$('#galaxy').append(PrintRow());")
            if eval_end == -1:
                self.error_str = 'parse error (1) cannot find start (and end) of packed function'
                return None
            # if we are here, probably galaxy script is not scrambled
            # eval_end is pointing at correct location, need to figure eval_start
            rows_end_str = "$('#galaxy').append(PrintSelector(fleet_shortcut));"
            eval_start = self.script_body.find(rows_end_str)
            if eval_start == -1:
                self.error_str = 'parse error (3) cannot find start of unpacked function'
                return None
            eval_start += len(rows_end_str)
            eval_text = self.script_body[eval_start:eval_end]
            eval_text = eval_text.strip()
            eval_text = 'var row = []; ' + eval_text + '\nreturn row;'
            #
            ctx = js_runtime.compile(eval_text)
            self.galaxy_rows = ctx.exec_(eval_text)
        else:
            # packed, as usual (uni4)
            eval_end = self.script_body.find("$('#galaxy').append(PrintRow());")
            if eval_end == -1:
                self.error_str = 'parse error(2) cannot find end of function'
                return None
            eval_text = self.script_body[eval_start:eval_end]
            eval_text = eval_text.strip()
            # ^^ [eval(function(p,a,c,k,e,d){e=function(c){r... ...141|7866|u0426'.split('|')))]
            eval_text = eval_text[5:-1]
            # ^^ [function(p,a,c,k,e,d){e=functi... ...0426'.split('|'))]
            eval_res = js_runtime.eval(eval_text)
            # Now, eval_res is a string:
            # row[12]={"planet":12,"id_planet":54448,"ally_planet":0,"metal":0,"crystal":0, ...
            eval_res = 'var row = []; ' + eval_res + "\nreturn row;"
            ctx = js_runtime.compile(eval_res)
            self.galaxy_rows = ctx.exec_(eval_res)

        return self.galaxy_rows
