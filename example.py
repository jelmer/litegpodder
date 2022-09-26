import logging
from aiohttp import web
from litegpodder.api import LitegpodderApp, Device, Subscription, create_app


class ExampleApp(LitegpodderApp):

    def get_devices(self, username):
        return [Device(id='abcdef', caption='gPodder on pixel', type='phone',
                       subscriptions=27)]

    def update_device(self, username, device):
        pass

    def sync_subscriptions_down(self, username, deviceid, since=0):
        return (["http://feeds.feedburner.com/linuxoutlaws"], [], 1)

    def sync_subscriptions_up(self, username, deviceid, add, remove):
        return 1, {}

    def get_subscriptions(self, username, deviceid):
        return [Subscription(
            website="http://sixgun.org",
            description="The hardest-hitting Linux podcast around",
            title="Linux Outlaws",
            author="Sixgun Productions",
            url="http://feeds.feedburner.com/linuxoutlaws",
            position_last_week=1,
            subscribers=1954,
            mygpo_link="http://gpodder.net/podcast/11092",
            logo_url="http://sixgun.org/files/linuxoutlaws.jpg",
            scaled_logo_url="http://gpodder.net/logo/64/fa9fd87a4f9e488096e52839450afe0b120684b4.jpg")]

    def sync_episodes_down(self, username, podcast_url=None, since=0,
                           device=None, aggregated=False):
        return ([], 1)

    def sync_episodes_up(self, username, actions):
        return 1, {}


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
args = parser.parse_args()

logging.basicConfig(level=logging.INFO, format='%(message)s')

app = create_app(ExampleApp(), lambda u, p: True)

web.run_app(app, port=args.port, host=args.listen_address)
