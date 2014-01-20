

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


RETARGET_TIMESPAN = 14 * 24 * 60 * 60

def get_standard_target(protocol_info, targets, timestamps, height):
    if len(targets) <= height - 1:
        raise None

    prev_target = targets[height - 1]

    if (height % 2016) != 0:
        return prev_target

    start_timestamp = timestamps[height - 2016]
    end_timestamp = timestamps[height - 1]

    timespan = end_timestamp - start_timestamp

    if timespan < RETARGET_TIMESPAN // 4:
        timespan = RETARGET_TIMESPAN // 4

    elif timespan > RETARGET_TIMESPAN * 4:
        timespan = RETARGET_TIMESPAN * 4

    new_target = (prev_target * timespan) // RETARGET_TIMESPAN

    return bits_to_target(target_to_bits(new_target))

