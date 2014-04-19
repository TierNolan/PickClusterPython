from __future__ import absolute_import, division, print_function, unicode_literals

import hashlib

import bitcoin.byte_array_codec
import network.network

BAC = bitcoin.byte_array_codec
Net = network.network

class MessageDecoder(object):

    def __init__(self, protocol_info):
        self.protocol_info = protocol_info

    def decode_message(self, buf):
        assert(isinstance(buf, bytearray))
        byte_stream = BAC.BinDecoder(buf)
        try:
            start = byte_stream.get_int() & 0xFFFFFFFF
            command = byte_stream.get_string(12)
            length = byte_stream.get_int()
            crc = byte_stream.get_int()

            if length < 0 or length > self.protocol_info.get_max_message_size():
                raise Net.DecodeError

            data = byte_stream.get_string(length)
        except BAC.DecoderEOF:
            return None, buf

        if start != self.protocol_info.get_message_start():
            raise Net.DecodeError

        sha256 = hashlib.sha256()
        sha256.update(data)
        digest = sha256.digest()
        sha256 = hashlib.sha256()
        sha256.update(digest)
        digest = sha256.digest()
        digest_stream = BAC.BinDecoder(digest)

        if digest_stream.get_int() == crc:
            return (command, data), byte_stream.get_remaining_buf()

    def encode_message(self, msg):
        command = msg[0]
        data = msg[1]
        byte_out_stream = BAC.BinEncoder()

        if len(command) > 12:
            raise Net.EncodeError
        if len(command) < 12:
            command += "\0" * (command - 12)

        if len(data) > self.protocol_info.get_max_message_size():
            raise Net.EncodeError

        sha256 = hashlib.sha256()
        sha256.update(data)
        digest = sha256.digest()
        sha256 = hashlib.sha256()
        sha256.update(digest)
        digest = sha256.digest()
        digest_stream = BAC.BinDecoder(digest)
        crc = digest_stream.get_int()

        byte_out_stream.put_int(self.protocol_info.get_message_start)
        byte_out_stream.put_string(command)
        byte_out_stream.put_int(len(data))
        byte_out_stream.put_int(crc)
        byte_out_stream.put_string(data)

        return byte_out_stream.as_string()
