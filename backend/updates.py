import json
import logging
import re
import urllib.request

from version import __version__

log = logging.getLogger('mp3.updates')

RELEASES_API = 'https://api.github.com/repos/efebalci569-dot/mp3-donusturucu/releases/latest'


def parse_version(tag):
    tag = (tag or '').strip()
    if tag.startswith('v'):
        tag = tag[1:]
    if not re.fullmatch(r'\d+(\.\d+)*', tag):
        return None
    return tuple(int(x) for x in tag.split('.'))


def _fetch_json(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': f'MP3Donusturucum/{__version__}',
        'Accept': 'application/vnd.github+json',
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode('utf-8'))


def check_latest(current, fetch=_fetch_json):
    # Geliştirme/CI sürümlerinde (0.0.0-dev gibi) kontrol yapılmaz.
    mine = parse_version(current)
    if mine is None:
        return None
    try:
        data = fetch(RELEASES_API)
        tag = data.get('tag_name') or ''
        latest = parse_version(tag)
        if latest and latest > mine:
            return {'available': True, 'version': tag, 'url': data.get('html_url')}
    except Exception as e:
        log.info('sürüm kontrolü yapılamadı: %s', e)
    return None
