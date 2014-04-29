from __future__ import absolute_import, division, print_function, unicode_literals


class Handler(object):

    def __init__(self, node):
        self.node = node

    def poll(self):
        pass

    def required_messages(self):
        return ()

    def polling_rate(self):
        return None

    def on_connect(self, peer_id, peer_handle, hostname, ip, port):
        pass

    def handle_message(self, peer_id, peer_handle, command, message):
        pass