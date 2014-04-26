from __future__ import absolute_import, division, print_function, unicode_literals

import bitcoin.protocols
import network.network
import multiprocessing
import sys
import logging
import bitcoin.node
import time

import logmanager.logmanager

Protocols = bitcoin.protocols
Net = network.network
MP = multiprocessing
LM = logmanager.logmanager
NODE = bitcoin.node

if __name__ == '__main__':
    MP.freeze_support()

    log_queue = LM.start_log_server(logging.DEBUG, "log", "pick_cluster.log")

    #node = Net.PeerManager(Protocols.MAIN_NET_INFO, log_queue)
    node = NODE.Node(log_queue, 10000)

    node.start()

    time.sleep(1)

    node.connect("localhost", 18333)

    sys.stdin.readline()

    node.shutdown()