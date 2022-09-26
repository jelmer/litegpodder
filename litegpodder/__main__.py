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


from datetime import datetime
import json
import logging
import os
from aiohttp import web
from .api import LitegpodderApp, Device, Subscription, create_app, Action


class MainApp(LitegpodderApp):

    def __init__(self, path):
        self.path = path

    def _devices_path(self, username):
        p = os.path.join(self.path, username, 'devices')
        os.makedirs(p, exist_ok=True)
        return p

    def _subscriptions_path(self, username, deviceid):
        p = os.path.join(self.path, username, 'subscriptions', deviceid)
        os.makedirs(p, exist_ok=True)
        return p

    def get_devices(self, username):
        devices_path = self._devices_path(username)
        for e in os.scandir(devices_path):
            if not e.name.endswith('.json'):
                continue
            deviceid = e.name[:-5]
            with open(e.path, 'r') as f:
                js = json.load(f)
            yield Device(
                id=deviceid,
                caption=js.get('caption'),
                type=js.get('type'),
                subscriptions=len(js.get('subscriptions', [])))

    def update_device(self, username, device):
        devices_path = self._devices_path(username)
        with open(os.path.join(devices_path, device.id + '.json'), 'w') as f:
            json.dump(
                {'caption': device.caption, 'type': device.type}, f, indent=4)

    def sync_subscriptions_down(self, username, deviceid, since=0):
        subscriptions_path = self._subscriptions_path(username, deviceid)
        if since == 0:
            a = set()
        else:
            with open(os.path.join(subscriptions_path, str(since)), 'r') as f:
                a = set(json.load(f))

        latest_path = os.path.join(subscriptions_path, 'latest')
        try:
            latest = int(os.readlink(latest_path))
        except FileNotFoundError:
            latest = 0
            b = set()
        else:
            with open(latest_path, 'r') as f:
                b = set(json.load(f))

        add = list(b.difference(a))
        remove = list(a.difference(b))

        return (add, remove, latest)

    def sync_subscriptions_up(self, username, deviceid, add, remove):
        subscriptions_path = self._subscriptions_path(username, deviceid)
        latest_path = os.path.join(subscriptions_path, 'latest')

        try:
            latest = int(os.readlink(latest_path))
        except FileNotFoundError:
            latest = 0
            subs = set()
        else:
            with open(latest_path, 'r') as f:
                subs = set(json.load(f))

        subs.update(add)
        subs.difference_update(remove)

        nextlatest = latest + 1

        with open(os.path.join(subscriptions_path, str(nextlatest)), 'w') as f:
            json.dump(list(subs), f, indent=4)

        os.symlink(str(nextlatest), latest_path)

        return nextlatest, {}

    def sync_episodes_down(self, username, podcast_url=None, since=0,
                           device=None, aggregated=False):
        os.makedirs(os.path.join(self.path, username), exist_ok=True)
        p = os.path.join(self.path, username, 'actions')
        try:
            with open(p, 'r') as f:
                lines = list(f.readlines())
        except FileNotFoundError:
            lines = []
        actions = []
        for line in lines[since:]:
            js = json.loads(line)
            js['timestamp'] = datetime.strptime(
                js['timestamp'], '%Y-%m-%dT%H:%M:%S')
            actions.append(Action(**js))
        return actions, len(lines)

    def sync_episodes_up(self, username, actions):
        os.makedirs(os.path.join(self.path, username), exist_ok=True)
        p = os.path.join(self.path, username, 'actions')

        with open(p, 'a') as f:
            for action in actions:
                f.write(json.dumps(action) + '\n')
        try:
            with open(p, 'r') as f:
                lineno = len(list(f.readlines()))
        except FileNotFoundError:
            lineno = 0
        return lineno, {}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-l",
        "--listen-address",
        dest="listen_address",
        default="localhost",
        help=(
            "Bind to this address. "
            "Pass in path for unix domain socket. [%(default)s]"
        ),
    )
    parser.add_argument(
        "-p",
        "--port",
        dest="port",
        type=int,
        default=8080,
        help="Port to listen on. [%(default)s]",
    )
    parser.add_argument(
        "-d",
        dest="datadir",
        default=".",
        help="Path to datadir")
    parser.add_argument(
        "--htpasswd",
        dest="htpasswd",
        help="Credentials file")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(message)s')

    if not args.htpasswd:
        def check_password(username, passwd):
            return True
    else:
        import bcrypt

        creds = {}
        with open(args.htpasswd, 'rb') as f:
            for line in f:
                (username, pwhash) = line.strip().split(b':')
                creds[username.decode()] = pwhash

        def check_password(username, passwd):
            try:
                expected = creds[username]
            except KeyError:
                return False
            try:
                return bcrypt.checkpw(passwd.encode(), expected)
            except ValueError:
                return False

    app = create_app(MainApp(args.datadir), check_password)

    web.run_app(app, port=args.port, host=args.listen_address)


if __name__ == '__main__':
    main()
