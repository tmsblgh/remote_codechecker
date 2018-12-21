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

logger = logging.getLogger('CLIENT - ANALYZE')
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
    parser = argparse.ArgumentParser(description=".....")

    log_args = parser.add_argument_group("log arguments", """.....""")

    log_args.add_argument('-b', '--build', type=str,
                          dest='build_command', help="...")

    log_args.add_argument('-id', '--id', type=str,
                          dest='id', help="...")

    args = parser.parse_args()

    try:
        with tempfile.NamedTemporaryFile(suffix='.zip') as zip_file:
            command = ["python2", "tu_collector.py"]
            command.append("-b")
            command.append("%s" % args.build_command)
            command.append("-z")
            command.append("%s" % zip_file.name)

        process = subprocess.Popen(command,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            
        process.wait()

        transport = TSocket.TSocket('localhost', 9090)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        client = RemoteAnalyze.Client(protocol)
        transport.open()

        with open(zip_file.name, 'rb') as source_file:
            file_content = source_file.read()

        try:
            response = client.analyze(args.id, file_content)
            logger.info('Stored sources for id %s', args.id)
        except InvalidOperation as e:
            print('InvalidOperation: %r' % e)

        # Close!
        transport.close()

    except Thrift.TException as tx:
        print('%s' % (tx.message))


if __name__ == "__main__":
    main()
