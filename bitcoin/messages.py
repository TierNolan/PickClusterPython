from __future__ import absolute_import, division, print_function, unicode_literals

import bitcoin.byte_array_codec

BAC = bitcoin.byte_array_codec

def target_to_bits(i):
    neg = i < 0

    i = abs(i)

    if i:
        byte_count = 1 + (i.bit_length() // 8)
    else:
        byte_count = 0

    if byte_count > 255:
        raise Exception

    encoded = byte_count << 24

    if byte_count < 3:
        encoded |= i << -(byte_count * 8 - 24)
    else:
        encoded |= i >> (byte_count * 8 - 24)

    if neg:
        encoded |= 0x00800000

    return encoded


def bits_to_target(encoded):
    neg = (encoded & 0x00800000) != 0

    byte_count = encoded >> 24

    encoded &= 0x007FFFFF

    if byte_count < 3:
        i = encoded >> -(byte_count * 8 - 24)
    else:
        i = encoded << (byte_count * 8 - 24)

    if neg:
        return -i
    else:
        return i


class TargetBits(object):

    def __init__(self, i):
        self.__i = i
        self.__encoded = target_to_bits(i)

    def get_target(self):
        return self.__i

    def get_encoded(self):
        return self.__encoded


CLIENT_NAME = "PickCluster"

class NetworkAddress(object):
    def __init__(self, timestamp, services, address, port):
        self.__timestamp = timestamp
        self.__services = services
        self.__address = address
        self.__port = port
        self.__is_ip4 = self.__address[0:10] == ("\x00" * 10 + "\xFF" * 2)

    def get_address(self):
        a = self.__address


class VerAck(object):

    def __init__(self):
        pass

    def decode(self, data):
        pass

    def encode(self):
        return bytearray()

class Version(object):

    def __init__(self, version=0, services=0, timestamp=0, address_to=None, address_from=None, connect_id=0, client_name=CLIENT_NAME, height=0, relay=0):
        self.__version = version
        self.__services = services
        self.__timestamp = timestamp
        self.__address_to = address_to
        self.__address_from = address_from
        self.__connect_id = connect_id
        self.__client_name = client_name
        self.__height = height
        self.__relay = relay

    def decode(self, data):
        decode = BAC.BinDecoder(data)

        self.__version = decode.get_int()
        self.__services = decode.get_long()
        self.__timestamp = decode.get_int()
        self.__address_to = decode.get_net_address()
