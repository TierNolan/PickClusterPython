from __future__ import absolute_import, division, print_function, unicode_literals

import bitcoin.byte_array_codec
import network.network
import binascii

BAC = bitcoin.byte_array_codec
NET = network.network

PROTOCOL_VERSION = 70003
PROTOCOL_SERVICES = 0
PROTOCOL_MIN_VERSION = 60000

CLIENT_NAME = "/PickCluster/"

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


class VarString(object):
    def __init__(self, uni=None, b=None):
        self.uni = uni
        self.ba = b

    def decode(self, version, decoder):
        length = decoder.get_var_int()
        self.ba = decoder.get_byte_array(length)
        self.uni = None

    def encode(self, version, encoder):
        if not self.ba:
            try:
                self.ba = bytearray(self.uni.encode('ascii'))
            except UnicodeEncodeError:
                self.ba = None
                raise NET.EncodeError, "Unable to convert variable string to byte array"

        encoder.put_var_int(len(self.ba))
        encoder.put_byte_array(self.ba)

    def get_string(self):
        if self.uni:
            return self.uni

        try:
            return unicode(self.ba, 'ascii')
        except UnicodeDecodeError:
            return None

    def decode_string(self):
        if not self.uni:
            self.uni = unicode(str(self.ba), 'ascii')

    def __repr__(self):
        if self.uni:
            return "{%s}" % self.uni
        else:
            return binascii.hexlify(self.ba)

IP4_PREFIX = bytearray(b"\x00" * 10 + b"\xff" * 2)


class NetworkAddress(object):
    def __init__(self, timestamp=0, services=0, address=bytearray(16), port=0):
        self.timestamp = timestamp
        self.services = services
        self.address = address
        self.port = port

    def decode(self, version, decoder):
        if version != 0:
            self.timestamp = decoder.get_int()

        self.services = decoder.get_ulong()
        self.address = decoder.get_byte_array(16)
        decoder.set_endian(BAC.BE)
        self.port = decoder.get_ushort()
        decoder.set_endian(BAC.LE)

    def encode(self, version, encoder):
        if version != 0:
            encoder.put_int(self.timestamp)

        encoder.put_long(self.services)
        encoder.put_byte_array(self.address)
        encoder.set_endian(BAC.BE)
        encoder.put_short(self.port)
        encoder.set_endian(BAC.LE)

    def get_host_string(self):
        if self.address[0:12] == IP4_PREFIX:
            return (u"%d" + 3 * u".%d") % tuple(self.address[12:16])
        else:
            return (u"%d" + 15 * u":%d") % tuple(self.address[0:16])

    def __repr__(self):
        if self.timestamp and self.timestamp != 0:
            return "{%d, %08x, %s, %d}" % (self.timestamp, self.services, self.get_host_string(), self.port)
        else:
            return "{%08x, %s, %d}" % (self.services, self.get_host_string(), self.port)

class VerAck(object):

    def __init__(self):
        pass

    def decode(self, version, decoder):
        pass

    def encode(self, version, encoder):
        pass

    def __repr__(self):
        return "{VerAck}"


class Version(object):

    def __init__(self, version=0, services=0, timestamp=0, address_to=None, address_from=None, connect_id=0,
                 client_name=VarString(CLIENT_NAME), height=0, relay=True):
        self.version = version
        self.services = services
        self.timestamp = timestamp
        self.address_to = address_to
        self.address_from = address_from
        self.connect_id = connect_id
        self.client_name = client_name
        self.start_height = height
        self.relay = relay

    def __repr__(self):
        return "{Version: version=%d, services=%d, timestamp=%d, address_to=%r, address_from=%r, conn_id=%d, client=%s, " \
               "height=%d, relay=%r" % (self.version, self.services, self.timestamp, self.address_to,
                                        self.address_from, self.connect_id, self.client_name, self.start_height,
                                        self.relay)

    def decode(self, version, decoder):
        self.version = decoder.get_int()

        if self.version < PROTOCOL_MIN_VERSION:
            return

        self.services = decoder.get_long()
        self.timestamp = decoder.get_long()

        self.address_to = NetworkAddress()
        self.address_to.decode(0, decoder)

        self.address_from = NetworkAddress()
        self.address_from.decode(0, decoder)

        self.connect_id = decoder.get_ulong()

        self.client_name = VarString()
        self.client_name.decode(0, decoder)
        self.client_name.decode_string()

        self.start_height = decoder.get_int()

        self.relay = self.version < 70001 or decoder.get_boolean()

    def encode(self, version, encoder):
        encoder.put_int(self.version)
        encoder.put_long(self.services)
        encoder.put_long(self.timestamp)
        self.address_to.encode(0, encoder)
        self.address_from.encode(0, encoder)
        encoder.put_long(self.connect_id)
        self.client_name.encode(version, encoder)
        encoder.put_int(self.start_height)
        if version == 0 or version >= 70001:
            encoder.put_boolean(self.relay)


message_map = {
    u"version": Version,
    u"verack": VerAck
}

byte_array_message_map = {}

for key, value in message_map.iteritems():
    s = key.encode('ascii')
    s += b"\00" * (12 - len(s))
    byte_array_message_map[s] = value


def get_message(command):
    return byte_array_message_map[str(command)]