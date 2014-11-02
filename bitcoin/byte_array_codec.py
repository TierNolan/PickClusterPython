from __future__ import absolute_import, division, print_function, unicode_literals

import struct

class DecoderError(Exception): pass
class DecoderEOF(DecoderError): pass

LE, BE = "<", ">"

LONG_MASK = 0xFFFFFFFFFFFFFFFFL

class BinDecoder(object):

    def __init__(self, b):
        assert(isinstance(b, bytearray))
        self.__buf = b
        self.__i = 0
        self.__endian = LE

    def set_endian(self, endian):
        self.__endian = endian

    def get_ubyte(self):
        return self.__get('B', 1)

    def get_byte(self):
        return self.__get('b', 1)

    def get_boolean(self):
        return self.get_byte() != 0

    def get_ushort(self):
        return self.__get('H', 2)

    def get_short(self):
        return self.__get('h', 2)

    def get_uint(self):
        return self.__get('I', 4)

    def get_int(self):
        return self.__get('i', 4)

    def get_var_int(self):
        b = self.get_ubyte()
        if b < 0xFD:
            return b
        elif b == 0xFD:
            return self.get_ushort()
        elif b == 0xFE:
            return self.get_uint()
        else:
            return self.get_ulong()

    def get_ulong(self):
        return self.__get('Q', 8)

    def get_long(self):
        return self.__get('q', 8)

    def __get(self, code, length):
        if self.__i + length > len(self.__buf):
            raise DecoderEOF
        section = self.__buf[self.__i:self.__i + length]
        value = struct.unpack((self.__endian + code).encode('utf-8'), section)[0]
        self.__i += length
        return value

    def get_string(self, length):
        value = str(self.get_byte_array(length))
        return value

    def get_byte_array(self, length):
        if self.__i + length > len(self.__buf):
            raise DecoderEOF
        value = self.__buf[self.__i: self.__i + length]
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
        import bitcoin.message
        return bitcoin.messages.NetworkAddress(timestamp, services, address, port)

    def get_remaining_buf(self):
        return bytearray(self.__buf[self.__i:])

class BinEncoder(object):

    def __init__(self):
        self.__buf = bytearray()
        self.__i = 0
        self.__endian = LE

    def set_endian(self, endian):
        self.__endian = endian

    def put_byte(self, b):
        b &= 0xFF
        self.put_byte_array(self.call_struct_pack(self.__endian + 'B', b))

    def put_boolean(self, b):
        if b:
            self.put_byte(1)
        else:
            self.put_byte(0)

    def put_short(self, s):
        s &= 0xFFFF
        self.put_byte_array(self.call_struct_pack(self.__endian + 'H', s))

    def put_int(self, i):
        i &= 0xFFFFFFFF
        self.put_byte_array(self.call_struct_pack(self.__endian + 'I', i))

    def put_var_int(self, i):
        i &= LONG_MASK
        if i < 0xFD:
            self.put_byte(i)
        elif i <= 0xFFFF:
            self.put_byte(0xFD)
            self.put_short(i)
        elif i <= 0xFFFFFFFF:
            self.put_byte(0xFE)
            self.put_int(i)
        else:
            self.put_byte(0xFF)
            self.put_long(i)

    def put_long(self, l):
        l &= LONG_MASK
        self.put_byte_array(self.call_struct_pack(self.__endian + 'Q', l))

    def call_struct_pack(self, t, value):
        type_str = t.encode('utf-8')
        return struct.pack(type_str, value)

    def put_byte_array(self, buf):
        for b in buf:
            self.__buf.append(b)

    def as_byte_array(self):
        return bytearray(self.__buf)