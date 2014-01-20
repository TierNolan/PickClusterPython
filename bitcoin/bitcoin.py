import binutils.byte_array_codec as BAS
import network.network as Net
import hashlib


class MessageDecoder(object):

    def __init__(self, protocol_info):
        self.protocol_info = protocol_info

    def decode_message(self, buf):
        assert(isinstance(buf, bytearray))
        byte_stream = BAS.BinDecoder(buf)
        try:
            start = byte_stream.get_int() & 0xFFFFFFFF
            command = byte_stream.get_string(12)
            length = byte_stream.get_int()
            crc = byte_stream.get_int()

            if length < 0 or length > self.protocol_info.get_max_message_size():
                raise Net.DecodeError

            data = byte_stream.get_string(length)
        except BAS.DecoderEOF:
            return None, buf

        if start != self.protocol_info.get_message_start():
            raise Net.DecodeError

        sha256 = hashlib.sha256()
        sha256.update(data)
        digest = sha256.digest()
        sha256 = hashlib.sha256()
        sha256.update(digest)
        digest = sha256.digest()
        digest_stream = BAS.BinDecoder(digest)

        if digest_stream.get_int() == crc:
            return (command, data), byte_stream.get_remaining_buf()

    def encode_message(self, msg):
        command = msg[0]
        data = msg[1]
        byte_out_stream = BAS.BinEncoder()

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
        digest_stream = BAS.BinDecoder(digest)
        crc = digest_stream.get_int()

        byte_out_stream.put_int(self.protocol_info.get_message_start)
        byte_out_stream.put_string(command)
        byte_out_stream.put_int(len(data))
        byte_out_stream.put_int(crc)
        byte_out_stream.put_string(data)

        return byte_out_stream.as_string()






