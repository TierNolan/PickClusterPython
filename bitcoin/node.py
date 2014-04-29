from __future__ import absolute_import, division, print_function, unicode_literals

import network.network
import bitcoin.protocols
import Queue
import logmanager.logmanager
import bitcoin.messages
import bitcoin.ping_manager
import bitcoin.bitcoin_codec
import time
import binascii

Net = network.network
Messages = bitcoin.messages
Protocols = bitcoin.protocols
LM = logmanager.logmanager
hexlify = binascii.hexlify


class PeerHandle(object):

    def __init__(self, node, hostname, ip, port, peer_id, outgoing):
        self.node = node
        self.hostname = hostname
        self.ip = ip
        self.port = port
        self.peer_id = peer_id
        self.outgoing = outgoing
        self.version = 0
        self.tolerance = 100
        self.ping_nonce = 0
        self.ping_time = None
        self.latency = None

    def __repr__(self):
        return "{id=%d, %s : %d, outgoing=%r, version=%d}" % \
               (self.peer_id, self.hostname, self.port, self.outgoing, self.version)

    def bad_peer(self, message, percent):
        self.tolerance -= percent
        LM.info("Bad peer %s: %s (%d), tolerance remaining %d" % (self.hostname, message, percent, self.tolerance))
        if self.tolerance <= 0:
            self.node.get_peer_manager().disconnect(self.peer_id)

    def set_version(self, version):
        self.version = version
        self.node.get_peer_manager().set_version(self.peer_id, version)

    def send_message(self, command, message):
        self.node.send_message(self.peer_id, self.version, command, message)


class QueueElement(object):
    def __init__(self, handler):
        self.t = time.time() + handler.polling_rate()
        self.handler = handler


class Node(LM.LoggingProcess):

    CMD_SHUTDOWN, CMD_CONNECT = range(2)

    def __init__(self, log_queue, port, protocol_info):
        self.__protocol_info = protocol_info
        self.__message_codec = None
        self.__peer_manager = None
        self.__peer_map = None
        self.__own_ip = None
        self.__own_port = None
        self.__handlers = None
        self.__handlers_map = None
        self.__handlers_queue = None
        super(Node, self).__init__(log_queue=log_queue, name="Node Manager", target=self._execute, args=())

    def get_peer_manager(self):
        return self.__peer_manager

    def get_peer_handles(self):
        return self.__peer_map.values()

    def connect(self, hostname, port):
        self.mp_queue_put((self.CMD_CONNECT, hostname, port))

    def shutdown(self):
        LM.info("Attempting node shutdown")
        self.mp_queue_put((self.CMD_SHUTDOWN, ))
        self.join()

    def send_message(self, peer_id, version, command, msg):
        self.__peer_manager.send_message(peer_id, version, command, msg)

    def handle_connect(self, hostname, ip, port, peer_id, outgoing):
        peer_handle = PeerHandle(self, hostname, ip, port, peer_id, outgoing)
        self.__peer_map[peer_id] = peer_handle
        if outgoing:
            version_message = Messages.Version(
                version=Messages.PROTOCOL_VERSION,
                services=Messages.PROTOCOL_SERVICES,
                timestamp=int(time.time()),
                address_to=Messages.NetworkAddress(None, 0, ip, port),
                address_from=Messages.NetworkAddress(None, Messages.PROTOCOL_SERVICES, self.__own_ip, self.__own_port),
            )
            self.send_message(peer_id, peer_handle.version, u"version", version_message)
        for handler in self.__handlers:
            handler.on_connect(peer_id, peer_handle, hostname, ip, port)

    def __add_polled_handler(self, new_element):
        i = len(self.__handlers_queue)
        for element in reversed(self.__handlers_queue):
            if element.t >= new_element.t:
                break
            i -= 1
        self.__handlers_queue.insert(i, new_element)

    def __get_polled_handler(self):
        if len(self.__handlers_queue) == 0:
            return None

        t = time.time()

        newest = self.__handlers_queue[-1]

        if newest.t < t:
            handler = newest.handler
            poll_time = handler.polling_rate()
            newest.t += poll_time
            if newest.t < t:
                newest.t = t + poll_time
            del self.__handlers_queue[-1]
            self.__add_polled_handler(newest)

            return newest.handler
        else:
            return None

    def handle_disconnect(self, hostname, port, peer_id):
        LM.info("Disconnected peer %s:%d (%d)" % (hostname, port, peer_id))
        del self.__peer_map[peer_id]
        LM.info("%d peers connected" % len(self.__peer_map))

    def handle_message(self, peer_id, command, message):
        peer_handle = self.__peer_map[peer_id]
        if peer_handle:
            if command == u"version":
                self.handle_version(peer_id, peer_handle, command, message)
            elif command == u"verack":
                self.handle_verack(peer_id, peer_handle, command, message)
            else:
                handlers = self.__handlers_map.get(command)
                if handlers:
                    for handler in handlers:
                        handler.handle_message(peer_id, peer_handle, command, message)
        else:
            LM.info("Unknown peer with id %d" % peer_id)

    def handle_version(self, peer_id, peer_handle, command, version_msg):
        if peer_handle.version != 0:
            peer_handle.bad_peer("Received a second version message", 100)
        else:
            peer_version = version_msg.version
            if peer_version > Messages.PROTOCOL_VERSION:
                peer_handle.set_version(Messages.PROTOCOL_VERSION)
            else:
                peer_handle.set_version(peer_version)

            if not peer_handle.outgoing:
                version_reply_message = Messages.Version(
                    version=Messages.PROTOCOL_VERSION,
                    services=Messages.PROTOCOL_SERVICES,
                    timestamp=int(time.time()),
                    address_to=Messages.NetworkAddress(None, 0, peer_handle.ip, peer_handle.port),
                    address_from=Messages.NetworkAddress(None, Messages.PROTOCOL_SERVICES, self.__own_ip,
                                                         self.__own_port),
                    )
                self.send_message(peer_id, peer_handle.version, "version", version_reply_message)

        LM.info("Version %d received from %s:%d, using %d" % (version_msg.version, peer_handle.hostname,
                                                              peer_handle.port, peer_handle.version))
        self.send_message(peer_id, peer_handle.version, "verack", Messages.VerAck())

    def handle_verack(self, peer_id, peer_handle, command, verack_message):
        pass

    def __register_handler(self, handler):
        if handler.polling_rate():
            self.__add_polled_handler(QueueElement(handler))
        self.__handlers.append(handler)
        commands = handler.required_messages()
        for command in commands:
            try:
                command_handlers = self.__handlers_map[command]
            except KeyError:
                command_handlers = None

            if not command_handlers:
                command_handlers = []
                self.__handlers_map[command] = command_handlers
            command_handlers.append(handler)

    def __at_start(self):
        self.__peer_map = {}
        self.__own_ip = bytearray(16)
        self.__own_port = 0
        self.__handlers_map = {}
        self.__handlers = []
        self.__handlers_queue = []
        self.__register_handler(bitcoin.ping_manager.PingManager(self))
        self.__peer_manager = Net.PeerManager(self.__protocol_info, self.get_log_queue())
        self.__peer_manager.start()

    def _execute(self):

        LM.info("Starting Node Manager")

        self.__at_start()

        try:
            while not self._interrupted:
                while True:
                    try:
                        node_event = self._mp_queue_get_internal(False)
                    except Queue.Empty:
                        node_event = None
                    if not node_event:
                        break

                    cmd = node_event[0]

                    if cmd == self.CMD_SHUTDOWN:
                        self.__peer_manager.shutdown()
                        return
                    elif cmd == self.CMD_CONNECT:
                        hostname = node_event[1]
                        port = node_event[2]
                        LM.info("Attempting to connect to %s:%d" % (hostname, port))
                        self.__peer_manager.connect(hostname, port)

                polled_handler = True
                while polled_handler:
                    polled_handler = self.__get_polled_handler()
                    if polled_handler:
                        polled_handler.poll()

                try:
                    peer_event = self.__peer_manager.mp_queue_get(True, 0.25)
                except Queue.Empty:
                    peer_event = None
                if not peer_event:
                    continue

                event_type = peer_event[0]

                if event_type == self.__peer_manager.INFO_CONNECTED:
                    peer_id = peer_event[1]
                    hostname = peer_event[2]
                    ip = peer_event[3]
                    port = peer_event[4]
                    LM.info("Connected to %s:%d (%d)" % (hostname, port, peer_id))
                    self.handle_connect(hostname, ip, port, peer_id, True)
                elif event_type == self.__peer_manager.INFO_CONNECT_FAILED:
                    peer_id = peer_event[1]
                    hostname = peer_event[2]
                    port = peer_event[3]
                    LM.info("Connection to %s:%d failed (%d)" % (hostname, port, peer_id))
                elif event_type == self.__peer_manager.INFO_MSG_RECEIVED:
                    peer_id = peer_event[1]
                    decoded = peer_event[2]
                    self.handle_message(peer_id, decoded[0], decoded[1])
                elif event_type == self.__peer_manager.INFO_DISCONNECTED:
                    peer_id = peer_event[1]
                    hostname = peer_event[2]
                    port = peer_event[3]
                    self.handle_disconnect(hostname, port, peer_id)
                else:
                    LM.info("Unknown event type %d" % event_type)

        finally:
            self.__peer_manager.shutdown()