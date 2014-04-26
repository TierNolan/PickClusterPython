from __future__ import absolute_import, division, print_function, unicode_literals

import socket
import multiprocessing
import network.network
import bitcoin.protocols
import Queue
import logmanager.logmanager

Net = network.network
Protocols = bitcoin.protocols
LM = logmanager.logmanager


class Node(LM.LoggingProcess):

    CMD_SHUTDOWN, CMD_CONNECT = range(2)

    def __init__(self, log_queue, port):
        self.__peer_manager = None
        super(Node, self).__init__(log_queue=log_queue, name="Node Manager", target=self._execute, args=())

    def connect(self, hostname, port):
        self.mp_queue_put((self.CMD_CONNECT, hostname, port))

    def shutdown(self):
        LM.info("Attempting node shutdown")
        self.mp_queue_put((self.CMD_SHUTDOWN, ))
        self.join()

    def _execute(self):

        LM.info("Starting Node Manager")

        self.__peer_manager = Net.PeerManager(Protocols.MAIN_NET_INFO, self.get_log_queue())
        self.__peer_manager.start()

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
                    port = peer_event[3]
                    LM.info("Connected to %s:%d (%d)" % (hostname, port, peer_id))
                elif event_type == self.__peer_manager.INFO_CONNECT_FAILED:
                    peer_id = peer_event[1]
                    hostname = peer_event[2]
                    port = peer_event[3]
                    LM.info("Connection to %s:%d failed (%d)" % (hostname, port, peer_id))
                else:
                    LM.info("Unknown event type %d" % event_type)

        finally:
            self.__peer_manager.shutdown()