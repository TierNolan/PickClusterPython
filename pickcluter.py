from __future__ import absolute_import, division, print_function, unicode_literals

import bitcoin.protocols
import network.network
import multiprocessing
import sys
import logging
import logmanager.logmanager

Protocols = bitcoin.protocols
Net = network.network
MP = multiprocessing
LM = logmanager.logmanager

if __name__ == '__main__':
    MP.freeze_support()

    log_queue = LM.start_log_server(logging.DEBUG, "log", "pick_cluster.log")

    p = Net.PeerManager(Protocols.MAIN_NET_INFO, log_queue)

    p.start()

    p.connect("localhost", 8333)

    result = p.mp_queue_get(True, None)

    print(result)

    sys.stdin.readline()

    p.shutdown()