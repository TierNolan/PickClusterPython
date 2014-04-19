from __future__ import absolute_import, division, print_function, unicode_literals

import socket
import multiprocessing
import Queue
import logmanager.logmanager

LM = logmanager.logmanager
mpQueue = multiprocessing.Queue

class DecodeError(Exception): pass
class EncodeError(Exception): pass


def get_server_socket(port):
    """Gets a server socket which listens on IP4 and IP6"""
    host = None
    s = None
    for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE):
        af, socket_type, protocol, canonical_name, sa = res
        try:
            s = socket.socket(af, socket_type, protocol)
        except socket.error as msg:
            s = None
            continue
        try:
            s.bind(sa)
            s.listen(1)
        except socket.error as msg:
            s.close()
            s = None
            continue
        break
    return s


def get_client_socket(host, port, timeout=5):
    """ Gets a client socket"""
    s = None
    for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM):
        af, socket_type, protocol, canonical_name, socket_address = res
        try:
            s = socket.socket(af, socket_type, protocol)
        except socket.error as msg:
            s = None
            continue
        try:
            s.settimeout(timeout)
            s.connect(socket_address)
        except socket.error as msg:
            s.close()
            s = None
            continue
        break
    return s


class PeerManager(LM.LoggingProcess):
    """ Container which holds active peers """

    INFO_CONNECTED, INFO_DISCONNECTED, INFO_CONNECT_FAILED, INFO_MSG_RECEIVED = range(4)

    CMD_CONNECT, CMD_DISCONNECT, CMD_SEND_MESSAGE, CMD_SHUTDOWN = range(4)

    def __init__(self, message_decoder, log_queue):
        self.__peers = {}
        self.__info_queue = None
        self.__interrupted = False
        self.__mp_in_queue = mpQueue()
        self.__mp_out_queue = mpQueue()
        self.__message_decoder = message_decoder
        super(PeerManager, self).__init__(log_queue=log_queue, name="Network", target=self._execute, args=())

    def mp_queue_get(self, block, timeout):
        return self.__mp_out_queue.get(block, timeout)

    def mp_queue_put(self, value):
        self.__mp_in_queue.put(value)

    def connect(self, hostname, port):
        self.mp_queue_put((self.CMD_CONNECT, hostname, port))

    def shutdown(self):
        self.mp_queue_put((self.CMD_SHUTDOWN, ))
        self.join()

    def _add_peer(self, peer):
        assert(isinstance(peer, Peer))
        self.__info_queue.put((self.INFO_CONNECTED, peer))

    def _remove_peer(self, peer):
        assert(isinstance(peer, Peer))
        self.__info_queue.put((self.INFO_DISCONNECTED, peer))

    def _connect_failed(self, peer):
        self.__info_queue.put((self.INFO_CONNECT_FAILED, peer))

    def _message_received(self, peer, msg):
        self.__info_queue.put((self.INFO_MSG_RECEIVED, peer, msg))

    def _peer_count(self):
        return len(self.__peers)

    def _execute(self):
        self.__info_queue = Queue.Queue()

        peer_id_counter = 1

        LM.info("Starting Network Peer Manager")

        try:
            while not self.__interrupted:
                while True:
                    try:
                        mp_data = self.__mp_in_queue.get(False)
                    except Queue.Empty:
                        mp_data = None
                    if not mp_data:
                        break

                    mp_command = mp_data[0]

                    if mp_command == self.CMD_CONNECT:
                        host = mp_data[1]
                        port = mp_data[2]
                        peer_thread = Peer(self, peer_id_counter, self.__message_decoder)
                        print ("connecting to %d %s %d" % (peer_id_counter, host, port))
                        peer_thread.connect(host, port)
                        peer_thread.start()
                    elif mp_command == self.CMD_DISCONNECT:
                        peer_id = mp_data[1]
                        p = self.__peers.get(peer_id)
                        if p:
                            p.interrupt()
                    elif mp_command == self.CMD_SHUTDOWN:
                        return
                try:
                    data = self.__info_queue.get(True, 0.25)
                except Queue.Empty as e:
                    continue
                command = data[0]
                peer = data[1]
                if command == self.INFO_CONNECTED:
                    self.__peers[peer_id_counter] = peer
                    self.__mp_out_queue.put((self.INFO_CONNECTED, peer.get_id()))
                    peer_id_counter += 1
                elif command == self.INFO_DISCONNECTED:
                    del self.__peers[peer.get_id()]
                    self.__mp_out_queue.put((self.INFO_DISCONNECTED, peer.get_id()))
                elif command == self.INFO_CONNECT_FAILED:
                    self.__mp_out_queue.put((self.INFO_CONNECT_FAILED, peer.get_id()))
                elif command == self.INFO_MSG_RECEIVED:
                    self.__mp_out_queue.put((self.INFO_MSG_RECEIVED, peer.get_id(), data[2]))
        finally:
            for p in self.__peers.values():
                p.interrupt()


class Peer(LM.LoggingThread):
    """ A connection to a peer """

    def __init__(self, peer_holder, peer_id, message_decoder):
        assert(isinstance(peer_holder, PeerManager))
        self.__host = None
        self.__port = None
        self.__s = None
        self.__peer_holder = peer_holder
        self.__message_decoder = message_decoder
        self.__interrupted = False
        self.__id = peer_id
        super(Peer, self).__init__(target=self._execute)

    def connect(self, host, port):
        self.__host = host
        self.__port = port

    def set_socket(self, s):
        assert(isinstance(s, socket.socket))
        self.__s = s

    def interrupt(self):
        self.__interrupted = True

    def get_id(self):
        return self.__id

    def _execute(self):
        if self.__s is None:
            self.__s = get_client_socket(self.__host, self.__port)
        if self.__s is None:
            self.__peer_holder._connect_failed(self)
            return
        self.__peer_holder._add_peer(self)
        try:
            try:
                self.__s.settimeout(0.25)
                buf = bytearray()
                while not self.__interrupted:
                    try:
                        chunk = self.__s.recv(4096)
                    except socket.timeout:
                        continue
                    if not chunk:
                        break
                    buf.extend(chunk)
                    msg, buf = self.__message_decoder.decode_message(buf)
                    if msg:
                        self.__peer_holder._message_received(self, msg)
            except socket.error as msg:
                pass
            finally:
                try:
                    self.__s.shutdown(socket.SHUT_RDWR)
                finally:
                    self.__s.close()
        finally:
            self.__peer_holder._remove_peer(self)