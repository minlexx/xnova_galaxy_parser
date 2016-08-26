import requests
from . import xn_logger

logger = xn_logger.get(__name__, debug=False)


def xnova_authorize(xn_host, xn_login, xn_password) -> dict:
    # This is only for debugging!
    # print('Content-Type: text/plain; charset=utf-8')
    # print()

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

    custom_headers = {
        'Referer': 'https://uni5.xnova.su',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': '*/*',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4',
        'Accept-Encoding': 'gzip, deflate, br',
        'Origin': 'https://uni5.xnova.su',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:48.0) Gecko/20100101 Firefox/48.0',
        'X-Requested-With': 'XMLHttpRequest'
    }

    # print(postdata, post_url)

    logger.info('Trying to authorize in XNova, url = {0} ...'.format(post_url))

    r = requests.post(post_url, data=postdata, allow_redirects=False, headers=custom_headers)
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
        logger.warn('Uni4 auth failed')
        if xn_host.startswith('uni5'):
            if ('PHPSESSID' not in cookies_dict) or ('session_id' not in cookies_dict):
                logger.warn('Uni5 auth failed')
                return None
    logger.info('Login OK')
    return cookies_dict
