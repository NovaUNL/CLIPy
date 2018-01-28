import os
import requests
from http.cookiejar import LWPCookieJar
import logging

from CLIPy import urls

log = logging.getLogger(__name__)
__active_sessions__ = []

http_headers = {'user-agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:1.0) Gecko/20100101 CLIPy'}


class Session:

    def __init__(self, username, password, cookies=os.getcwd() + '/cookies'):
        log.info('Creating clip session (Cookie file:{})'.format(cookies))
        self.__cookie_file__ = cookies
        self.authenticated = False
        self.__requests_session__ = requests.Session()
        self.__requests_session__.cookies = LWPCookieJar(cookies)
        self.username = username
        self.password = password
        for session in __active_sessions__:
            if session.__cookie_file__ == self.__cookie_file__:
                raise Exception("Attempted to share a cookie file")

        if not os.path.exists(cookies):
            self.save()
            log.info('Created empty cookie file')
        __active_sessions__.append(self)
        self.authenticate()

    def save(self):
        self.__requests_session__.cookies.save(ignore_discard=True)

    def authenticate(self):
        request = self.__requests_session__.post(
            urls.ROOT, headers=http_headers, data={'identificador': self.username, 'senha': self.password})
        if "password" in request.text:
            raise Exception("CLIP authentication failed")
        self.authenticated = True
        log.info('Successfully authenticated')
        self.save()

    def get(self, url):
        log.info('Fetching:' + url)
        return self.__requests_session__.get(url, headers=http_headers)

    def __exit__(self, exc_type, exc_val, exc_tb):
        __active_sessions__.remove(self)
