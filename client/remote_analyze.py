#!/usr/bin/env python3

import sys
sys.path.append('../gen-py')
import argparse
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

logger = logging.getLogger('CLIENT')
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
    # --- Handling of command line arguments --- #

    parser = argparse.ArgumentParser(description=".....")

    log_args = parser.add_argument_group("log arguments", """.....""")
    log_args = log_args.add_mutually_exclusive_group(required=True)

    log_args.add_argument('-b', '--build', type=str,
                          dest='command', help="...")

    parser.add_argument('-o', '--output', type=str, dest='output', help="...")

    args = parser.parse_args()

    # --- Do the job. --- #

    try:
        # Make socket
        transport = TSocket.TSocket('localhost', 9090)

        # Buffering is critical. Raw sockets are very slow
        transport = TTransport.TBufferedTransport(transport)

        # Wrap in a protocol
        protocol = TBinaryProtocol.TBinaryProtocol(transport)

        # Create a client to use the protocol encoder
        client = RemoteAnalyze.Client(protocol)

        # Connect!
        transport.open()

        command = "python tu_collector.py -b \"" + args.command + "\" -z sources.zip"

        logger.info("Command: %s" % command)

        process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        process.wait()

        f = open('sources.zip', 'rb')
        file_content = f.read()
        f.close()

        try:
            response = client.analyze(args.command, file_content)
            with open('output.zip', 'wb') as zipf:
                try:
                    zipf.write(response)
                except Exception:
                    logger.error("Failed to extract received ZIP.")
        except InvalidOperation as e:
            print('InvalidOperation: %r' % e)

        # Close!
        transport.close()

    except Thrift.TException as tx:
        print('%s' % (tx.message))


if __name__ == "__main__":
    main()
