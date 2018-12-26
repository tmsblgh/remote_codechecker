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

LOGGER = logging.getLogger('CLIENT - ANALYZE')
LOGGER.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
LOGGER.addHandler(ch)


def analyze(args):
    try:
        transport = TSocket.TSocket('localhost', 9090)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        client = RemoteAnalyze.Client(protocol)
        transport.open()

        try:
            analyzeId = client.getId()
            LOGGER.info('Received id %s', analyzeId)
        except InvalidOperation as e:
            print('InvalidOperation: %r' % e)

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

        with open(zip_file.name, 'rb') as source_file:
            file_content = source_file.read()

        try:
            response = client.analyze(analyzeId, file_content)
            LOGGER.info('Stored sources for id %s', analyzeId)
        except InvalidOperation as e:
            LOGGER.error('InvalidOperation: %r' % e)

        # Close!
        transport.close()

    except Thrift.TException as thrift_exception:
        LOGGER.error('%s' % (thrift_exception.message))

def get_status(args):
    try:
        transport = TSocket.TSocket('localhost', 9090)
        transport = TTransport.TBufferedTransport(transport)
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        client = RemoteAnalyze.Client(protocol)
        transport.open()

        try:
            response = client.getStatus(args.id)
            LOGGER.info('Status of analysis: %s', response)
        except InvalidOperation as e:
            LOGGER.error('InvalidOperation: %r' % e)

        # Close!
        transport.close()

    except Thrift.TException as thrift_exception:
        LOGGER.error('%s' % (thrift_exception.message))

def get_results(args):
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
                    LOGGER.info('Stored the results of analysis %s', args.id)
                except Exception:
                    LOGGER.error("Failed to store received ZIP.")
                    
        except InvalidOperation as e:
            LOGGER.error('InvalidOperation: %r' % e)

        transport.close()

    except Thrift.TException as thrift_exception:
        LOGGER.error('%s' % (thrift_exception.message))


def main():
    parser = argparse.ArgumentParser(description=".....")

    subparsers = parser.add_subparsers(help='sub-command help')

    parser_analyze = subparsers.add_parser('analyze', help='analyze help')
    parser_analyze.add_argument('-b', '--build', type=str,
                          dest='build_command', required=True, help="...")
    parser_analyze.set_defaults(func=analyze)

    parser_status = subparsers.add_parser('status', help='status help')
    parser_status.add_argument('-id', '--id', type=str,
                          dest='id', required=True, help="...")
    parser_status.set_defaults(func=get_status)

    parser_results = subparsers.add_parser('results', help='results help')
    parser_results.add_argument('-id', '--id', type=str,
                          dest='id', required=True, help="...")
    parser_results.set_defaults(func=get_results)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
