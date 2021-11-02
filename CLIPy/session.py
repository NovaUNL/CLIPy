import os
from datetime import datetime, timedelta
from threading import Semaphore
from time import sleep

import requests
from http.cookiejar import LWPCookieJar
import logging
from bs4 import BeautifulSoup
import psycopg2

from . import urls
from . import config

log = logging.getLogger(__name__)
__active_sessions__ = []
__auth_lock__ = Semaphore()

http_headers = {'user-agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:1.0) Gecko/20100101 CLIPy'}


class AuthenticationFailure(Exception):
    def __init__(self, *args, **kwargs):
        super(Exception, self).__init__(*args, *kwargs)


class Session:
    """
    A session behaves like a browser session, maintaining (some) state across requests.
    """

    def __init__(self, cookies=os.getcwd() + '/cookies'):
        log.debug('Creating clip session (Cookie file:{})'.format(cookies))
        self.__cookie_file__ = cookies
        self.authenticated = False
        self.__requests_session__ = requests.Session()
        self.__requests_session__.cookies = LWPCookieJar(cookies)
        credentials = config.CLIP_CREDENTIALS
        self.__username__ = credentials['USERNAME']
        self.__password__ = credentials['PASSWORD']
        if config.CACHE_DB:
            self.__session_cache__ = SessionCache(config.CACHE_DB)
        else:
            self.__session_cache__ = None
        for session in __active_sessions__:
            if session.__cookie_file__ == self.__cookie_file__:
                raise Exception("Attempted to share a cookie file")

        if not os.path.exists(cookies):
            self.save()
            log.debug('Created empty cookie file')
        __active_sessions__.append(self)
        self.__last__authentication = None

    def save(self):
        """
        Saves cookies to disk for reuse
        """
        self.__requests_session__.cookies.save(ignore_discard=True)

    def authenticate(self):
        """
        Sets up auth cookies for this session
        """
        __auth_lock__.acquire()
        try:
            time_limit = datetime.now() - timedelta(minutes=15)
            if self.__last__authentication is None or self.__last__authentication < time_limit:
                while True:
                    try:
                        log.info("Requesting auth")
                        request = self.__requests_session__.post(
                            urls.ROOT,
                            headers=http_headers,
                            data={'identificador': self.__username__, 'senha': self.__password__},
                            timeout=10)
                        log.info("Response for auth received")
                        break
                    except requests.exceptions.Timeout:
                        log.warning(f"Request timed out: {urls.ROOT}")
                        sleep(5)
                if "password" in request.text:
                    raise AuthenticationFailure("CLIP authentication failed")
                self.authenticated = True
                log.info('Successfully authenticated with CLIP')
                self.__last__authentication = datetime.now()
                self.save()
            else:
                self.__last__authentication = datetime.now()

        finally:
            __auth_lock__.release()

    def get(self, url: str) -> requests.Response:
        """
        Fetches a remote URL using an HTTP GET method using the current session attributes
        :param url: URL to fetch
        :return: Request response
        """
        log.debug('Fetching:' + url)
        self.authenticate()
        return self.__requests_session__.get(url, headers=http_headers, timeout=30)

    def post(self, url: str, data: {str: str}) -> requests.Response:
        """
        Fetches a remote URL using an HTTP POST method using the current session attributes
        :param url: URL to fetch
        :param data: POST data dict
        :return: Request response
        """
        log.debug(f'Fetching: {url} with params {data}')
        self.authenticate()
        return self.__requests_session__.post(url, data=data, headers=http_headers, timeout=30)

    def get_simplified_soup(self, url: str, post_data=None) -> BeautifulSoup:
        """
        | Fetches a remote URL using an HTTP GET method using the current session attributes.
        | Then parses the response text cleaning tags which aren't useful for parsing
        | If the post field is filled the HTTP POST method is used instead

        :param url: URL to fetch
        :param post_data: If filled, upgrades the request to an HTTP POST with this being the data dict
        :return: Parsed html tree
        """
        cached_data = self.__session_cache__.read(url)
        if cached_data is not None:
            return read_and_clean_response(cached_data)

        if post_data is None:
            html = self.get(url).text
        else:
            html = self.post(url, data=post_data).text
        self.__session_cache__.store(url, html)
        return read_and_clean_response(html)

    def get_broken_simplified_soup(self, url: str, post_data=None) -> BeautifulSoup:
        """
        | Fetches a remote URL using an HTTP GET method using the current session attributes.
        | Then parses the response text with an heavy parser (allowing for broken HTML)
            cleaning tags which aren't useful for parsing
        | If the post field is filled the HTTP POST method is used instead

        :param url: URL to fetch
        :param post_data: If filled, upgrades the request to an HTTP POST with this being the data dict
        :return: Parsed html tree
        """
        cached_data = self.__session_cache__.read(url)
        if cached_data is not None:
            return read_and_clean_broken_response(cached_data)

        if post_data is None:
            html = self.get(url).text
        else:
            html = self.post(url, data=post_data).text
        self.__session_cache__.store(url, html)
        return read_and_clean_broken_response(html)

    def get_file(self, url: str) -> (bytes, str):
        """
        Fetches a file from a remote URL using an HTTP GET method using the current session attributes
        :param url: URL to fetch
        :return: ``file_bytes, mimetype`` tuple
        """
        response = self.get(url)
        if 'content-type' not in response.headers:
            return None

        return response.content, response.headers['content-type']

    def __exit__(self, exc_type, exc_val, exc_tb):
        __active_sessions__.remove(self)


def clean_soup(soup: BeautifulSoup):
    """
    Removes tags not useful for parsing.
    :param soup: Parsed HTML `soup`
    :return: Cleaned `soup`
    """
    for tag in soup.find_all('script'):
        tag.decompose()
    for tag in soup.find_all('link'):
        tag.decompose()
    for tag in soup.find_all('img'):
        tag.decompose()
    for tag in soup.find_all('input'):
        tag.decompose()
    for tag in soup.find_all('br'):
        tag.decompose()
    for tag in soup.find_all('meta'):
        if 'content' in tag.attrs:
            continue
        tag.decompose()
    tag = soup.find(summary="FCTUNL, emblema")
    if tag:
        tag.decompose()


def read_and_clean_response(html: str) -> BeautifulSoup:
    """
    Reads a response and simplifies its result.
    :param html: The html of the page that is to be simplified
    :return: Simplified result
    """
    soup = BeautifulSoup(html, 'html.parser')
    clean_soup(soup)
    return soup


def read_and_clean_broken_response(html: str) -> BeautifulSoup:
    """
    Reads a response and simplifies its result using a parser which allows broken HTML.
    :param html: The html of the page that is to be simplified
    :return: Simplified result
    """
    soup = BeautifulSoup(html, 'html5lib')
    clean_soup(soup)
    return soup


class SessionCache:
    def __init__(self, settings):
        self.__conn__ = psycopg2.connect(
            dbname=settings['NAME'],
            host=settings['HOST'],
            port=settings['PORT'],
            user=settings['USER'],
            password=settings['PASSWORD'])
        self.__lock__ = Semaphore(value=1)

    def read(self, url: str):
        """
        Obtains the cached content of an URL
        :param url: The address of the potentially stored page
        :return: The HTML of the stored page (null if not stored)
        """
        self.__lock__.acquire()
        try:
            cur = self.__conn__.cursor()
            cur.execute("SELECT html FROM page_cache WHERE url=(%s);", (url,))
            row = cur.fetchone()
            cur.close()
            if row:
                return row[0]
        finally:
            self.__lock__.release()

    def store(self, url: str, html: str):
        """
        Caches the content of an URL
        :param url: The address of the current page
        :param html: Page content
        """
        self.__lock__.acquire()
        try:
            cur = self.__conn__.cursor()
            cur.execute(
                "INSERT INTO page_cache (url, html, capture) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (url) DO UPDATE SET html=EXCLUDED.html, capture=EXCLUDED.capture",
                (url, html, datetime.now()))
            self.__conn__.commit()
            cur.close()
        finally:
            self.__lock__.release()
