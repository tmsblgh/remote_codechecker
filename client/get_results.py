#!/usr/bin/env python3

"""
Client for handling remote analyze requests with CodeChecker.
"""

import sys
import subprocess
import argparse
import zipfile
import logging
from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol

sys.path.append('../gen-py')
from remote_analyze_api import RemoteAnalyze
from remote_analyze_api.ttypes import InvalidOperation

logger = logging.getLogger('CLIENT - GET RESULTS')
logger.setLevel(logging.INFO)
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
LOGGER.addHandler(ch)
LOGGER.addHandler(fh)


def main():
    parser = argparse.ArgumentParser(description=".....")

    log_args = parser.add_argument_group("log arguments", """.....""")
    log_args = log_args.add_mutually_exclusive_group(required=True)

    log_args.add_argument('-id', '--id', type=str,
                          dest='id', help="...")

    args = parser.parse_args()

    try:
        transport = TSocket.TSocket('localhost', 9090)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        client = RemoteAnalyze.Client(protocol)
        transport.open()

        try:
            response = client.getResults(args.id)
            with open(args.id + '.zip', 'wb') as source:
                try:
                    source.write(response)
                    logger.info('Stored the results of analysis %s', args.id)
                except Exception:
                    logger.error("Failed to store received ZIP.")
                    
        except InvalidOperation as e:
            print('InvalidOperation: %r' % e)

        transport.close()

    except Thrift.TException as thrift_exception:
        LOGGER.error('%s' % (thrift_exception.message))


if __name__ == "__main__":
    main()
