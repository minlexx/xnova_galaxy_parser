import requests
from . import xn_logger

logger = xn_logger.get(__name__, debug=False)


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
        post_url = 'https://uni5.xnova.su/index/login/?'

    logger.info('Trying to authorize in XNova, url = {0} ...'.format(post_url))

    r = requests.post(post_url, data=postdata, allow_redirects=False)
    # print(r.content)  # empty
    # print(r.text)     # also empty
    cookies_dict = {}
    for single_cookie in r.cookies.iteritems():
        cookies_dict[single_cookie[0]] = single_cookie[1]
    # print(cookies_dict)
    if ('x_id' not in cookies_dict) and ('x_secret' not in cookies_dict) \
            and ('x_uni' not in cookies_dict):
        # uni4 auth failed, try uni5
        logger.warn('Uni4 auth failed')
        if xn_host.startswith('uni5'):
            if ('u5_secret' not in cookies_dict) and ('u5_id' not in cookies_dict):
                logger.warn('Uni5 auth failed')
                return None
    logger.info('Login OK')
    return cookies_dict
