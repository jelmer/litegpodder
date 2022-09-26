# litegpodder
# Copyright (C) 2022 Jelmer Vernooĳ <jelmer@jelmer.uk>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; version 3
# of the License or (at your option) any later version of
# the License.
#
# This program is distributed in the hope that it will be uselful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.

"""Lite implementation of the gpodder API.

"""

from aiohttp import web, BasicAuth
from datetime import datetime
from dataclasses import dataclass
import logging
from typing import Optional, Iterable, Tuple, List, Dict
import uuid


routes = web.RouteTableDef()


@routes.post('/api/2/auth/{username}/login.json')
async def handle_login(request):
    try:
        ba = BasicAuth.decode(request.headers['Authorization'])
    except KeyError:
        raise web.HTTPUnauthorized(text='Authorization header missing')
    if ba.login != request.match_info['username']:
        raise web.HTTPBadRequest(text="username mismatch")
    if not request.app['check_password'](ba.login, ba.password):
        raise web.HTTPUnauthorized(text='invalid credentials')

    sessionid = str(uuid.uuid4())
    request.app['sessions'][sessionid] = ba.login
    resp = web.json_response({}, status=200)
    resp.set_cookie('sessionid', sessionid)
    return resp


@routes.post('/api/2/auth/{username}/logout.json')
async def handle_logout(request):
    try:
        sessionid = request.cookies['sessionid']
    except KeyError:
        pass
    del request.app['sessions'][sessionid]
    resp = web.json_response({}, status=200)
    resp.del_cookie('sessionid')
    return resp


async def check_auth(request):
    username = request.match_info['username']
    session_username = request.app['sessions'][request.cookies['sessionid']]
    if username != session_username:
        raise web.HTTPBadRequest(text="username mismatch")


@routes.post('/api/2/devices/{username}/{deviceid}.json')
async def handle_device_update(request):
    await check_auth(request)
    json = await request.json()
    device = Device(
        id=request.match_info['deviceid'],
        caption=json['caption'],
        type=json['type'])
    request.app['app'].update_device(request.match_info['username'], device)
    return web.json_response({}, status=200)


TYPES = ['laptop', 'mobile']


@dataclass
class Device:

    id: str
    caption: str
    type: str
    subscriptions: Optional[int] = None

    def json(self):
        ret = {
            'id': self.id,
            'caption': self.caption,
            'type': self.type,
        }
        if self.subscriptions is not None:
            ret['subscriptions'] = self.subscriptions
        return ret


@routes.get('/api/2/devices/{username}.json')
async def handle_devices(request):
    await check_auth(request)
    devices = request.app['app'].get_devices(request.match_info['username'])
    return web.json_response([device.json() for device in devices])


@dataclass
class Action:

    podcast: str
    episode: str
    device: str
    action: str
    timestamp: datetime
    started: Optional[int] = None
    position: Optional[int] = None
    total: Optional[int] = None
    guid: Optional[str] = None

    def json(self):
        ret = {
            'podcast': self.podcast,
            'episode': self.episode,
            'device': self.device,
            'action': self.action,
            'timestamp': self.timestamp.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        if self.guid is not None:
            ret['guid'] = self.guid
        if self.started is not None:
            ret['started'] = self.started
            ret['position'] = self.position
            ret['total'] = self.total
        return ret


@routes.get('/api/2/episodes/{username}.json')
async def handle_episodes_down(request):
    await check_auth(request)
    podcast_url = request.query.get('podcast')
    since = int(request.query.get('since', '0'))
    device = request.query.get('device')
    aggregated = request.query.get('aggregated') == 'True'
    username = request.match_info['username']

    actions, timestamp = request.app['app'].sync_episodes_down(
        username,
        podcast_url=podcast_url, since=since,
        device=device, aggregated=aggregated)
    return web.json_response({
        'actions': [action.json() for action in actions],
        'timestamp': timestamp,
    })


@routes.post('/api/2/episodes/{username}.json')
async def handle_episodes_up(request):
    await check_auth(request)
    username = request.match_info['username']
    timestamp, rewritten_urls = request.app['app'].sync_episodes_up(
        username, await request.json())
    return web.json_response({
        'timestamp': timestamp,
        'update_urls': list(rewritten_urls.items())})


@dataclass
class Subscription:

    website: str
    description: str
    title: str
    author: str
    url: str
    position_last_week: int
    subscribers: int
    mygpo_link: str
    logo_url: str
    scaled_logo_url: str

    def json(self):
        return {
            "website": self.website,
            "description": self.description,
            "title": self.title,
            "author": self.author,
            "url": self.url,
            "position_last_week": self.position_last_week,
            "subscribers": self.subscribers,
            "mygpo_link": self.mygpo_link,
            "logo_url": self.logo_url,
            "scaled_logo_url": self.scaled_logo_url
        }


@routes.get('/subscriptions/{username}/{deviceid}.{format}')
async def handle_device_subscriptions(request):
    await check_auth(request)
    format = request.match_info['format']
    if format != 'json':
        raise NotImplementedError
    username = request.match_info['username']
    deviceid = request.match_info['deviceid']
    ret = []
    for subscription in request.app['app'].get_subscriptions(
            username, deviceid):
        ret.append(subscription.json())
    return web.json_response(ret, status=200)


@routes.get('/api/2/subscriptions/{username}/{deviceid}.json')
async def handle_sync_down_subscriptions(request):
    await check_auth(request)
    since = int(request.query.get('since', '0'))
    username = request.match_info['username']
    deviceid = request.match_info['deviceid']
    (add, remove, timestamp) = request.app['app'].sync_subscriptions_down(
        username, deviceid, since=since)
    return web.json_response({
        'add': add, 'remove': remove, 'timestamp': timestamp}, status=200)


@routes.post('/api/2/subscriptions/{username}/{deviceid}.json')
async def handle_sync_up_subscriptions(request):
    await check_auth(request)
    username = request.match_info['username']
    deviceid = request.match_info['deviceid']
    js = await request.json()
    timestamp, rewritten_urls = request.app['app'].sync_subscriptions_up(
        username, deviceid, js['add'], js['remove'])
    return web.json_response({
        'timestamp': timestamp,
        'update_urls': list(rewritten_urls.items())})


class LitegpodderApp:

    def get_subscriptions(self, username: str,
                          deviceid: str) -> Iterable[Subscription]:
        raise NotImplementedError(self.get_subscriptions)

    def sync_subscriptions_down(self,
                                username: str, deviceid: str,
                                since: int = 0
                                ) -> Tuple[List[str], List[str], int]:
        raise NotImplementedError(self.sync_subscriptions_down)

    def sync_subscriptions_up(self, username: str, deviceid: str,
                              add: List[str],
                              remove: List[str]) -> Tuple[int, Dict[str, str]]:
        raise NotImplementedError(self.sync_subscriptions_up)

    def update_device(self, username: str, device: Device) -> None:
        raise NotImplementedError(self.update_device)

    def get_devices(self, username: str) -> Iterable[Device]:
        raise NotImplementedError(self.get_devices)

    def sync_episodes_down(self, username: str,
                           podcast_url: Optional[str] = None,
                           since: int = 0,
                           device: Optional[str] = None,
                           aggregated: bool = False
                           ) -> Tuple[List[Action], int]:
        raise NotImplementedError(self.sync_episodes_down)

    def sync_episodes_up(self, username: str,
                         actions: List[Action]) -> Tuple[int, Dict[str, str]]:
        raise NotImplementedError(self.sync_episodes_up)


def create_app(app, check_password):
    ret = web.Application()
    ret['app'] = app
    ret['check_password'] = check_password
    ret['sessions'] = {}
    ret.router.add_routes(routes)
    return ret
