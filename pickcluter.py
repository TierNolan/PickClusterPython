import bitcoin.protocols as Protocols
import network.network as Net
import multiprocessing as MP
import sys
import logging
import logmanager.logmanager as LM
import time

if __name__ == '__main__':
    MP.freeze_support()

    log_queue = LM.start_log_server(logging.DEBUG, "log", "pick_cluster.log")

    p = Net.PeerManager(Protocols.MAIN_NET_INFO, log_queue)

    p.start()

    p.connect("p2pool.tiernolan.org", 9332)

    result = p.mp_queue_get(True, None)

    print result

    sys.stdin.readline()

    p.shutdown()