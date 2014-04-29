from __future__ import absolute_import, division, print_function, unicode_literals

import bitcoin.node
import logmanager.logmanager
import bitcoin.handler
import bitcoin.messages
import random
import time

LM = logmanager.logmanager


class PingManager(bitcoin.handler.Handler):

    def __init__(self, node):
        self.ping_rate = 5
        super(PingManager, self).__init__(node)

    def poll(self):
        peer_handles = self.node.get_peer_handles()
        t = time.time()
        for peer_handle in peer_handles:
            nonce = random.randint(0, 0xFFFFFFFFFFFFFFFF)
            peer_handle.ping_nonce = nonce
            peer_handle.ping_time = t
            peer_handle.send_message("ping", bitcoin.messages.Ping(nonce))

    def required_messages(self):
        return "ping", "pong"

    def polling_rate(self):
        return self.ping_rate

    def on_connect(self, peer_id, peer_handle, hostname, ip, port):
        pass

    def handle_message(self, peer_id, peer_handle, command, message):
        if command == u"ping" and peer_handle.version > 60000:
            ping = message
            peer_handle.send_message("pong", bitcoin.messages.Pong(ping.nonce))
        elif command == u"pong":
            pong = message
            if peer_handle.ping_nonce and peer_handle.ping_time:
                if peer_handle.ping_nonce != 0 and peer_handle.ping_nonce == pong.nonce:
                    peer_handle.ping_none = None
                    delta_t = time.time() - peer_handle.ping_time
                    if 0 < delta_t < 30:
                        if not peer_handle.latency:
                            peer_handle.latency = delta_t
                        else:
                            peer_handle.latency = 0.25 * delta_t + 0.75 * peer_handle.latency