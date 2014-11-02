from __future__ import absolute_import, division, print_function, unicode_literals

import hashlib

import bitcoin.byte_array_codec
import network.network
import bitcoin.message

BAC = bitcoin.byte_array_codec


class MessageCodec(object):

    def __init__(self, protocol_info):
        self.protocol_info = protocol_info

    def decode_message(self, buf, version):
        assert(isinstance(buf, bytearray))
        byte_stream = BAC.BinDecoder(buf)
        try:
            start = byte_stream.get_int() & 0xFFFFFFFF
            command = byte_stream.get_string(12)
            length = byte_stream.get_int()
            crc = byte_stream.get_int()

            if length < 0 or length > self.protocol_info.get_max_message_size():
                raise network.network.DecodeError

            data = byte_stream.get_byte_array(length)
        except BAC.DecoderEOF:
            return None, buf

        if version == 0 and command != b"version\x00\x00\x00\x00\x00":
            return None, buf

        if start != self.protocol_info.get_message_start():
            raise network.network.DecodeError

        sha256 = hashlib.sha256()
        sha256.update(data)
        digest = sha256.digest()
        sha256 = hashlib.sha256()
        sha256.update(digest)
        digest = sha256.digest()
        digest_stream = BAC.BinDecoder(bytearray(digest))

        expected_crc = digest_stream.get_int()

        if expected_crc == crc:
            message_class = bitcoin.message.get_message(command)
            if message_class:
                message = message_class()
                decoder = BAC.BinDecoder(data)
                message.decode(version, decoder)
            else:
                message = None
            for i in range(12):
                if command[11 - i] != '\x00':
                    return (command[0:(12 - i)], message), byte_stream.get_remaining_buf()
        else:
            return None, buf

    def encode_message(self, version, command, msg):

        data_encoder = BAC.BinEncoder()
        msg.encode(version, data_encoder)

        data = data_encoder.as_byte_array()

        byte_out_stream = BAC.BinEncoder()

        command = bytearray(command, 'ascii')

        if len(command) > 12:
            raise network.network.EncodeError
        if len(command) < 12:
            command += b"\0" * (12 - len(command))

        if len(data) > self.protocol_info.get_max_message_size():
            raise network.network.EncodeError

        sha256 = hashlib.sha256()
        sha256.update(data)
        digest = sha256.digest()
        sha256 = hashlib.sha256()
        sha256.update(digest)
        digest = sha256.digest()
        digest = bytearray(digest)
        digest_stream = BAC.BinDecoder(digest)
        crc = digest_stream.get_int()

        byte_out_stream.put_int(self.protocol_info.get_message_start())
        byte_out_stream.put_byte_array(command)
        byte_out_stream.put_int(len(data))
        byte_out_stream.put_int(crc)
        byte_out_stream.put_byte_array(data)

        return byte_out_stream.as_byte_array()
