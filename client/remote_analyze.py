#!/usr/bin/env python3

"""
Client for handling remote analyze requests with CodeChecker.
"""

import sys
import argparse
import subprocess
import logging
from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol

sys.path.append('../gen-py')
from remote_analyze_api import RemoteAnalyze
from remote_analyze_api.ttypes import InvalidOperation

LOGGER = logging.getLogger('SERVER')
LOGGER.setLevel(logging.INFO)
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
    # --- Handling of command line arguments --- #

    parser = argparse.ArgumentParser(description=".....")

    log_args = parser.add_argument_group("log arguments", """.....""")
    log_args = log_args.add_mutually_exclusive_group(required=True)

    log_args.add_argument('-b', '--build', type=str,
                          dest='command', help="...")

    parser.add_argument('-o', '--output', type=str, dest='output', help="...")

    args = parser.parse_args()

    source_file = 'sources.zip'

    # --- Do the job. --- #

    try:
        transport = TSocket.TSocket('localhost', 9090)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        client = RemoteAnalyze.Client(protocol)
        transport.open()

        command = ["python2", "tu_collector.py"]
        command.append("-b")
        command.append("%s" % args.command)
        command.append("-z")
        command.append("%s" % source_file)

        process = subprocess.Popen(command,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)

        process.wait()

        with open(source_file, 'rb') as source_file:
            file_content = source_file.read()

        try:
            response = client.analyze(args.command, file_content)
            try:
                with open('output.zip', 'wb') as zipf:
                    zipf.write(response)
            except IOError:
                LOGGER.error("Failed to write out received ZIP.")
        except InvalidOperation as exception:
            LOGGER.error('InvalidOperation: %r' % exception)

        transport.close()

    except Thrift.TException as thrift_exception:
        LOGGER.error('%s' % (thrift_exception.message))


if __name__ == "__main__":
    main()