#!/usr/bin/env python
import hashlib
import random
import re
from urllib import unquote

from livestreamer.plugin import Plugin
from livestreamer.plugin.api import http, validate
from stream import HLSStream

TVPLAYER_STREAM_WEB_ENCRYPTED_URL = "http://live.tvplayer.com/stream-web-encrypted.php"
TVPLAYER_REFERER = ("http://assets.storage.uk.tvplayer.com.s3.amazonaws.com/web/"
                    "flash/secure_SSMPlayer_4-8-4.swf?nocache={0}".format(random.randint(1, 20000)))
FLASH_VERSION_STRING = "ShockwaveFlash/18.0.0.161"
TVPLAYER_ORIGIN = "http://assets.storage.uk.tvplayer.com.s3.amazonaws.com"
TVPLAYER_SECRET_KEY = "KADI4591AKCLLE"
USER_AGENT = "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36"

_url_re = re.compile(r"http://(?:www.)?tvplayer.com/watch/(.+)")
_hash_var = re.compile(r"""var hash="(.*)";""")
_exp_var = re.compile(r"""var exp="(\d+)";""")
_channel_map_re = re.compile(r"""/Colour/(\d+).png""")

_channel_schema = validate.Schema({
    "tvplayer":
        {u'endpoint': u'stream',
         u'response':
             {u'cc': bool,
              u'stream': validate.url(scheme=validate.any("http"))},
         u'time': unicode}
})


class TVPlayer(Plugin):
    @classmethod
    def can_handle_url(cls, url):
        match = _url_re.match(url)
        return match

    def _get_streams(self):
        url_match = _url_re.match(self.url)
        if url_match:
            # find the list of channels from the html in the page
            res = http.get(self.url)
            channel_map = _channel_map_re.search(res.text)
            if channel_map:
                channel_id = channel_map.group(1)

                # get the token_expiry and hash vars from the html page
                try:
                    var_token_expiry = _exp_var.findall(res.text)[0]
                    var_hash = unquote(_hash_var.findall(res.text)[0])
                except IndexError:
                    # page layout changed
                    raise

                # compute the key for the request
                key = hashlib.md5(var_token_expiry + TVPLAYER_SECRET_KEY).hexdigest()

                headers = {
                    "Hash": var_hash,
                    "Token-Expiry": var_token_expiry,
                    "Key": key,
                    "User-Agent": USER_AGENT,
                    "Referer": TVPLAYER_REFERER,
                    "X-Requested-With": FLASH_VERSION_STRING,
                    "Origin": TVPLAYER_ORIGIN
                }

                res = http.post(TVPLAYER_STREAM_WEB_ENCRYPTED_URL,
                                data=dict(id=channel_id),
                                headers=headers)
                stream_data = http.json(res, schema=_channel_schema)
                http.cookies.update(res.cookies)
                return HLSStream.parse_variant_playlist(self.session, stream_data['tvplayer']['response']['stream'])


__plugin__ = TVPlayer
