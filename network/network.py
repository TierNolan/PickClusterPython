from __future__ import absolute_import, division, print_function, unicode_literals

import socket
import Queue
import logmanager.logmanager
import bitcoin.byte_array_codec
import bitcoin.bitcoin_codec

LM = logmanager.logmanager

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

    CMD_CONNECT, CMD_DISCONNECT, CMD_SEND_MESSAGE, CMD_SHUTDOWN, CMD_SET_VERSION = range(5)

    def __init__(self, protocol_info, log_queue):
        self.__peers = {}
        self.__info_queue = None
        self.__protocol_info = protocol_info
        super(PeerManager, self).__init__(log_queue=log_queue, name="Network", target=self._execute, args=())

    def connect(self, hostname, port):
        self.mp_queue_put((self.CMD_CONNECT, hostname, port))

    def disconnect(self, peer_id):
        self.mp_queue_put((self.CMD_DISCONNECT, peer_id))

    def set_version(self, peer_id, version):
        self.mp_queue_put((self.CMD_SET_VERSION, peer_id, version))

    def shutdown(self):
        self.mp_queue_put((self.CMD_SHUTDOWN, ))
        self.join()

    def send_message(self, peer_id, version, command, message):
        self.mp_queue_put((self.CMD_SEND_MESSAGE, peer_id, version, command, message))

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

        LM.info("Starting Network Manager")

        try:
            while not self._interrupted:
                while True:
                    try:
                        mp_data = self._mp_queue_get_internal(False)
                    except Queue.Empty:
                        mp_data = None
                    if not mp_data:
                        break

                    mp_command = mp_data[0]

                    if mp_command == self.CMD_CONNECT:
                        host = mp_data[1]
                        port = mp_data[2]
                        peer_thread = Peer(self, peer_id_counter, self.__protocol_info)
                        peer_thread.connect(host, port)
                        peer_thread.start()
                    elif mp_command == self.CMD_DISCONNECT:
                        peer_id = mp_data[1]
                        p = self.__peers.get(peer_id)
                        if p:
                            p.interrupt()
                    elif mp_command == self.CMD_SEND_MESSAGE:
                        peer_id = mp_data[1]
                        version = mp_data[2]
                        command = mp_data[3]
                        message = mp_data[4]
                        p = self.__peers.get(peer_id)
                        p.peer_send_thread.send(version, command, message)
                    elif mp_command == self.CMD_SET_VERSION:
                        peer_id = mp_data[1]
                        version = mp_data[2]
                        p = self.__peers.get(peer_id)
                        if p:  # peer could shutdown while command is in transit
                            p.set_version(version)
                    elif mp_command == self.CMD_SHUTDOWN:
                        return
                try:
                    data = self.__info_queue.get(True, 0.25)
                except Queue.Empty:
                    continue
                command = data[0]
                peer = data[1]
                if command == self.INFO_CONNECTED:
                    self.__peers[peer_id_counter] = peer
                    self._mp_queue_put_internal((self.INFO_CONNECTED, peer.get_id(), peer.get_hostname(), peer.get_ip(),
                                                 peer.get_port()))
                    peer_id_counter += 1
                elif command == self.INFO_DISCONNECTED:
                    del self.__peers[peer.get_id()]
                    self._mp_queue_put_internal((self.INFO_DISCONNECTED, peer.get_id(), peer.get_hostname(),
                                                 peer.get_port()))
                elif command == self.INFO_CONNECT_FAILED:
                    self._mp_queue_put_internal((self.INFO_CONNECT_FAILED, peer.get_id(), peer.get_hostname(),
                                                 peer.get_port()))
                elif command == self.INFO_MSG_RECEIVED:
                    self._mp_queue_put_internal((self.INFO_MSG_RECEIVED, peer.get_id(), data[2]))
        finally:
            for p in self.__peers.values():
                p.interrupt()


def convert_ip(peer_name):
    if len(peer_name) == 2:
        s = socket.inet_aton(peer_name[0])
        ip = bytearray(16)
        ip[10:12] =  bytearray(b"\xFF\xFF")
        if len(s) != 4:
            return None
        ip[12:16] = s
        return ip
    elif len(peer_name) == 4:
        split = peer_name[0].split(":")
        if len(split) > 8:
            return None
        padded = False
        byte_array_code = bitcoin.byte_array_codec.BinEncoder()
        byte_array_code.set_endian(bitcoin.byte_array_codec.BE)

        if len(split) < 2:
            return None

        if len(split[0]) == 0:
            if len(split[1]) != 0:
                return None
            split = split[1:]

        l = len(split)
        if l < 2:
            return None

        if len(split[l - 1]) == 0:
            if len(split[l - 2]) != 0:
                return None
            split = split[0:l - 1]

        for word in split:
            if len(word) == 0:
                if padded:
                    return None
                padded = True
                i = 9 - len(split)
                while i > 0:
                    byte_array_code.put_short(0)
                    i -= 1
            else:
                as_int = int(word, 16)
                if as_int < 0 or as_int > 0xFFFF:
                    return None
                byte_array_code.put_short(as_int)
        return byte_array_code.as_byte_array()


class Peer(LM.LoggingThread):
    """ A connection to a peer """

    def __init__(self, peer_holder, peer_id, protocol_info):
        assert(isinstance(peer_holder, PeerManager))
        self.__host = None
        self.__port = None
        self.__s = None
        self.__ip = None
        self.__peer_holder = peer_holder
        self.__protocol_info = protocol_info
        self.__message_codec = bitcoin.bitcoin_codec.MessageCodec(self.__protocol_info)
        self.__interrupted = False
        self.__id = peer_id
        self.__version = 0
        self.peer_send_thread = None
        super(Peer, self).__init__(target=self._execute)

    def connect(self, host, port):
        self.__host = host
        self.__port = port

    def set_socket(self, s):
        assert(isinstance(s, socket.socket))
        self.__s = s

    def interrupt(self):
        self.__interrupted = True

    def set_version(self, version):
        self.__version = version

    def get_id(self):
        return self.__id

    def get_hostname(self):
        return self.__host

    def get_port(self):
        return self.__port

    def get_ip(self):
        return self.__ip

    def _execute(self):
        if self.__s is None:
            self.__s = get_client_socket(self.__host, self.__port)
        if self.__s is None:
            self.__peer_holder._connect_failed(self)
            return

        self.__ip = convert_ip(self.__s.getpeername())
        self.__peer_holder._add_peer(self)
        try:
            try:
                self.peer_send_thread = PeerSendThread(self.__s, self.__protocol_info, self)
                self.peer_send_thread.start()
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
                    msg = True
                    while msg and not self.__interrupted:
                        msg, buf = self.__message_codec.decode_message(buf, self.__version)
                        if msg:
                            self.__peer_holder._message_received(self, msg)

            except socket.error:
                pass
            finally:
                try:
                    self.__s.shutdown(socket.SHUT_RDWR)
                finally:
                    self.peer_send_thread.interrupt()
                    self.peer_send_thread.join()
                    self.__s.close()
        finally:
            self.__peer_holder._remove_peer(self)


class PeerSendThread(LM.LoggingThread):
    """ Peer send thread """

    def __init__(self, s, protocol_info, parent_peer):
        self.__s = s
        self.__protocol_info = protocol_info
        self.__message_codec = bitcoin.bitcoin_codec.MessageCodec(self.__protocol_info)
        self.__send_queue = Queue.Queue()
        self.__interrupted = False
        self.__parent_peer = parent_peer
        super(PeerSendThread, self).__init__(target=self._execute)

    def interrupt(self):
        self.__interrupted = True

    def send(self, version, command, message):
        self.__send_queue.put((version, command, message))

    def _execute(self):
        try:
            while not self.__interrupted:
                try:
                    msg = self.__send_queue.get(True, 0.25)
                except Queue.Empty:
                    msg = None
                    continue
                version = msg[0]
                command = msg[1]
                message = msg[2]
                encoded = self.__message_codec.encode_message(version, command, message)
                to_send = len(encoded)
                while to_send > 0:
                    to_send -= self.__s.send(encoded)
        finally:
            self.__parent_peer.interrupt()
