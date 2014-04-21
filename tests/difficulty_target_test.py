from __future__ import absolute_import, division, print_function, unicode_literals

import bitcoin.messages

Messages = bitcoin.messages

TEST_FULL_DIFFICULTY = False

def test_difficulty_full():
    """ Checks all 2 ** 32 possible int encodings, encode(decode(x)) == x """
    if not TEST_FULL_DIFFICULTY:
        print ("Full difficulty target encoding/decoding check: skipped")
        return

    print ("Running difficulty target encoding/decoding check")
    encoded = 0
    while encoded < 2 ** 32:
        decoded = Messages.bits_to_target(encoded)
        size = encoded >> 24

        # Mask off lower bytes, if the number is small
        if size == 0:
            masked = encoded & 0xFF000000
        elif size == 1:
            masked = encoded & 0xFFFF0000
        elif size == 2:
            masked = encoded & 0xFFFFFF00
        else:
            masked = encoded

        # If mantissa is zero, value must be zero
        if masked & 0x007FFFFF == 0:
            masked = 0

        # Shift mantissa left as most significant byte may only be zero if necessary
        while masked & 0x007F8000 == 0 and masked & 0x00007FFF != 0:
            masked = ((masked - 0x01000000) & 0xFF800000) | ((masked & 0x007FFFFF) << 8)

        reencoded = Messages.target_to_bits(decoded)
        assert(reencoded == masked), "re-encode of %x (value=%x) failed, gave %x, expected %x" % \
                                     (encoded, decoded, reencoded, masked)
        encoded += 1
        if encoded % 10000000 == 0:
            print ("Full test progress %0.2f%%" % ((100.0 * encoded) / 2 ** 32))

TARGET_TEST_VECTORS = [
    # decoder input, decoded, re-encoded
    (0x00000000, "0",          0),
    (0x00123456, "0",          0),
    (0x01003456, "0",          0),
    (0x02000056, "0",          0),
    (0x03000000, "0",          0),
    (0x04000000, "0",          0),
    (0x00923456, "0",          0),
    (0x01803456, "0",          0),
    (0x02800056, "0",          0),
    (0x03800000, "0",          0),
    (0x04800000, "0",          0),
    (0x01123456, "12",         0x01120000),
    (None,       "80",         0x02008000),
    (0x01fedcba, "-7E",        0x01fe0000),
    (0x02123456, "1234",       0x02123400),
    (0x03123456, "123456",     0x03123456),
    (0x04123456, "12345600",   0x04123456),
    (0x04923456, "-12345600",  0x04923456),
    (0x05009234, "92340000",   0x05009234),
    (0x20123456, "1234560000000000000000000000000000000000000000000000000000000000", 0x20123456),
    (
        0xff123456,
        "1234560000000000000000000000000000000000000000000000000000000000" +
        "0000000000000000000000000000000000000000000000000000000000000000" +
        "0000000000000000000000000000000000000000000000000000000000000000" +
        "0000000000000000000000000000000000000000000000000000000000000000" +
        "0000000000000000000000000000000000000000000000000000000000000000" +
        "0000000000000000000000000000000000000000000000000000000000000000" +
        "0000000000000000000000000000000000000000000000000000000000000000" +
        "00000000000000000000000000000000000000000000000000000000000000",
        0xff123456
    )
]


def test_difficulty_vectors():
    for vector in TARGET_TEST_VECTORS:
        encoded = vector[0]
        expected_decoded = int(vector[1], 16)
        expected_reencoded = vector[2]
        if encoded:
            decoded = Messages.bits_to_target(encoded)
            assert(decoded == expected_decoded), "Encoding of %x gave %x, expected %x" % \
                                                 (encoded, decoded, expected_decoded)
        reencoded = Messages.target_to_bits(expected_decoded)
        assert(reencoded == expected_reencoded), "Re-encoding of %x gave %x, expected %x" % \
                                                 (reencoded, reencoded, expected_reencoded)


def get_tests():
    return [
        ("Difficulty Target Encode/Decode Vectors", test_difficulty_vectors),
        ("Difficulty Target Full Test", test_difficulty_full, TEST_FULL_DIFFICULTY)
    ]

def get_name():
    return "Difficulty Target Tests"