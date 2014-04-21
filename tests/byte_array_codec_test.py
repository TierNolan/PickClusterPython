from __future__ import absolute_import, division, print_function, unicode_literals

import random
import binascii

import bitcoin.byte_array_codec

BAC = bitcoin.byte_array_codec

ByteEnc = BAC.BinEncoder
ByteDec = BAC.BinDecoder


def test_codec(endian, put_func, get_func, valid_range):
    r = []
    for i in range(0, 100):
        value = random.randrange(valid_range[0], valid_range[1])
        r.append(value)

    enc = BAC.BinEncoder()
    enc.set_endian(endian)

    for i in r:
        put_func(enc, i)

    dec = BAC.BinDecoder(enc.as_byte_array())
    dec.set_endian(endian)

    for i in range(0, 100):
        value = get_func(dec)
        assert(r[i] == value), "Decoded value %x does not match expected %x" % \
                               (value, r[i])


def test_signed_unsigned(bits, put_func, get_func, get_func_unsigned):
    test_codec(BAC.LE, put_func, get_func, (-(2 ** (bits - 1)), 2 ** (bits - 1) - 1))
    test_codec(BAC.LE, put_func, get_func_unsigned, (0, 2 ** bits - 1))
    test_codec(BAC.BE, put_func, get_func, (-(2 ** (bits - 1)), 2 ** (bits - 1) - 1))
    test_codec(BAC.BE, put_func, get_func_unsigned, (0, 2 ** bits - 1))


def test_byte_codec():
    test_signed_unsigned(8, ByteEnc.put_byte, ByteDec.get_byte, ByteDec.get_ubyte)


def test_short_codec():
    test_signed_unsigned(16, ByteEnc.put_short, ByteDec.get_short, ByteDec.get_ushort)


def test_int_codec():
    test_signed_unsigned(32, ByteEnc.put_int, ByteDec.get_int, ByteDec.get_uint)


def test_long_codec():
    test_signed_unsigned(64, ByteEnc.put_long, ByteDec.get_long, ByteDec.get_ulong)


def test_mixed_types():
    enc = BAC.BinEncoder()

    enc.put_byte(0x12)
    enc.put_short(0x1234)
    enc.put_int(0x12345678)
    enc.put_long(0x1234567811111111)

    b = bytearray(b'\x11\x22\x33\x44\x55\x66\x77\x88')
    enc.put_byte_array(b)

    dec = BAC.BinDecoder(enc.as_byte_array())
    assert(dec.get_byte() == 0x12)
    assert(dec.get_short() == 0x1234)
    assert(dec.get_int() == 0x12345678)
    assert(dec.get_long() == 0x1234567811111111)
    assert(dec.get_byte_array(len(b)) == b)


def test_endian():
    enc = BAC.BinEncoder()
    enc.set_endian(BAC.LE)
    enc.put_short(0x1234)
    enc.put_int(0x12345678)
    enc.put_long(0x1234567844444444)

    exp = binascii.unhexlify(b"3412785634124444444478563412")
    assert(enc.as_byte_array() == exp), "Endian error, got %s, expected %s" % \
                                                                (enc.as_byte_array(), exp)

    enc = BAC.BinEncoder()
    enc.set_endian(BAC.BE)
    enc.put_short(0x1234)
    enc.put_int(0x12345678)
    enc.put_long(0x1234567844444444)

    exp = binascii.unhexlify(b"1234123456781234567844444444")
    assert(enc.as_byte_array() == exp), "Endian error, got %s, expected %s" % \
                                                   (enc.as_byte_array(), exp)


def get_tests():
    return [
        ("Byte Encode/Decode Test", test_byte_codec),
        ("Short Encode/Decode Test", test_short_codec),
        ("Int Encode/Decode Test", test_int_codec),
        ("Long Encode/Decode Test", test_long_codec),
        ("Mixed Encode/Decode Test", test_mixed_types),
        ("Endian Test", test_endian)
    ]


def get_name():
    return "Byte Array Codec Tests"