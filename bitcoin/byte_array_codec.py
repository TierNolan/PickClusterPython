from __future__ import absolute_import, division, print_function, unicode_literals

import struct

class DecoderError(Exception): pass
class DecoderEOF(DecoderError): pass

LE, BE = "<", ">"


class BinDecoder(object):

    def __init__(self, s):
        self.__str = s
        self.__i = 0
        self.__endian = LE

    def set_endian(self, endian):
        self.__endian = endian

    def get_ubyte(self):
        return self.__get('B', 1)

    def get_byte(self):
        return self.__get('b', 1)

    def get_ushort(self):
        return self.__get('H', 2)

    def get_short(self):
        return self.__get('h', 2)

    def get_uint(self):
        return self.__get('I', 4)

    def get_int(self):
        return self.__get('i', 4)

    def get_ulong(self):
        return self.__get('Q', 8)

    def get_long(self):
        return self.__get('q', 8)

    def __get(self, code, length):
        if self.__i + length > len(self.__str):
            raise DecoderEOF
        section = self.__str[self.__i:self.__i + length]
        value = struct.unpack(self.__endian + code, section)[0]
        self.__i += length
        return value

    def get_string(self, length):
        if self.__i + length > len(self.__str):
            raise DecoderEOF
        value = self.__str[self.__i: self.__i + length]
        self.__i += length
        return value

    def get_byte_array(self, length):
        if self.__i + length > len(self.__str):
            raise DecoderEOF
        value = bytearray(self.__str[self.__i: self.__i + length])
        self.__i += length
        return value

    def get_net_address(self, timestamp_included):
        if timestamp_included:
            timestamp = self.get_int()
        else:
            timestamp = 0
        services = self.get_long()
        address = self.get_byte_array(16)
        port = self.get_short()
        import bitcoin.messages
        return bitcoin.messages.NetworkAddress(timestamp, services, address, port)


    def get_remaining_buf(self):
        return bytearray(self.__str[self.__i:])


class BinEncoder(object):

    def __init__(self):
        self.__str = ""
        self.__i = 0
        self.__endian = LE

    def set_endian(self, endian):
        self.__endian = endian

    def put_byte(self, b):
        b &= 0xFF
        self.__str += struct.pack(self.__endian + 'B', b)

    def put_short(self, s):
        s &= 0xFFFF
        self.__str += struct.pack(self.__endian + 'H', s)

    def put_int(self, i):
        i &= 0xFFFFFFFF
        self.__str += struct.pack(self.__endian + 'I', i)

    def put_long(self, l):
        l &= 0xFFFFFFFFFFFFFFFFL
        self.__str += struct.pack(self.__endian + 'Q', l)

    def put_string(self, s):
        self.__str += s

    def put_byte_array(self, buf):
        self.__str += str(buf)

    def as_string(self):
        return self.__str