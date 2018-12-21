#!/usr/bin/env python3

import sys
sys.path.append('../gen-py')
import subprocess
import zipfile
import logging
import zlib
import tempfile

from remote_analyze_api import RemoteAnalyze
from remote_analyze_api.ttypes import InvalidOperation

from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol

logger = logging.getLogger('CLIENT - GET ID')
logger.setLevel(logging.INFO)
fh = logging.FileHandler('../server.log')
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
logger.addHandler(ch)
logger.addHandler(fh)


def main():
    try:
        transport = TSocket.TSocket('localhost', 9090)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        client = RemoteAnalyze.Client(protocol)
        transport.open()

        try:
            response = client.getId()
            logger.info('Received id %s', response)
        except InvalidOperation as e:
            print('InvalidOperation: %r' % e)

        # Close!
        transport.close()

    except Thrift.TException as tx:
        print('%s' % (tx.message))


if __name__ == "__main__":
    main()
