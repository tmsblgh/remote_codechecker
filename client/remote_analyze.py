#!/usr/bin/env python3

import os
import sys
sys.path.append('../gen-py')
import argparse
import subprocess
import zipfile
import logging
import zlib
import tempfile
import json
import zipfile

from contextlib import AbstractContextManager

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


class RemoteAnalayzerClient(AbstractContextManager):
    def __init__(self, host, port):
        self.transport = TSocket.TSocket(host, port)
        self.transport = TTransport.TBufferedTransport(self.transport)
        self.protocol = TBinaryProtocol.TBinaryProtocol(self.transport)

    def __enter__(self):
        client = RemoteAnalyze.Client(self.protocol)
        self.transport.open()
        return client

    def __exit__(self, *exc_details):
        self.transport.close()


def analyze(args):
    """
    This method tries to collect files based on the build command for the
    remote analysis with tu_collector script to a zip file.

    If it was success it calls server's getId method to get an UUID for the
    analysis.

    Then the script saves the zip file to the workspace/{received-uuid}
    directory .
    """

    try:
        build_commands = {}
        tempfile_names = []

        if args.build_command:
            command = args.build_command
            for part in command.split(' '):
                if part.endswith('.cpp'):
                    file_path = part
                    break

            absolute_file_path = os.path.abspath(file_path)

            modified_command = command.replace(file_path, absolute_file_path)

            file_path = absolute_file_path

            build_commands[file_path] = modified_command
        else:
            with open(args.compilation_database) as json_file:
                compilation_database = json.load(json_file)
                for item in compilation_database:
                    command = item['command']
                    directory = item['directory']
                    file_name = item['file']

                    file_path = directory + file_name

                    modified_command = command.replace(file_name, file_path)
                    build_commands[file_path] = modified_command

        LOGGER.debug('%s', build_commands)

        for file_path in build_commands:
            with tempfile.NamedTemporaryFile(suffix='.zip') as zip_file:
                command = ["python2", "tu_collector.py"]
                command.append("-b")
                command.append("%s" % build_commands[file_path])
                command.append("-z")
                command.append("%s" % zip_file.name)

            process = subprocess.Popen(command,
                                       stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)

            process.wait()

            with zipfile.ZipFile(zip_file.name, 'a') as zipf:
                zipf.writestr('sources-root/build_command',
                              build_commands[file_path])
                zipf.writestr('sources-root/file_path', file_path)

            tempfile_names.append(zip_file.name)

        with RemoteAnalayzerClient(args.host, args.port) as client:
            try:
                analyzeId = client.getId()
                LOGGER.info('Received id %s', analyzeId)
            except InvalidOperation as e:
                logger.error('InvalidOperation: %r' % e)

            for tempfile_name in tempfile_names:
                with open(tempfile_name, 'rb') as source_file:
                    file_content = source_file.read()

                    try:
                        response = client.analyze(analyzeId, file_content)
                    except InvalidOperation as e:
                        LOGGER.error('InvalidOperation: %r' % e)

            LOGGER.info('Stored sources for id %s', analyzeId)

    except Thrift.TException as thrift_exception:
        LOGGER.error('%s' % (thrift_exception.message))


def get_status(args):
    """
    This method tries to get the status of the analysis from the server.
    """

    try:
        with RemoteAnalayzerClient(args.host, args.port) as client:
            try:
                response = client.getStatus(args.id)
                LOGGER.info('Status of analysis: %s', response)
            except InvalidOperation as e:
                LOGGER.error('InvalidOperation: %r' % e)

    except Thrift.TException as thrift_exception:
        LOGGER.error('%s' % (thrift_exception.message))


def get_results(args):
    """
    This method tries to get the results of the analysis from the server.
    """

    try:
        with RemoteAnalayzerClient(args.host, args.port) as client:
            try:
                response = client.getResults(args.id)
                with open(args.id + '.zip', 'wb') as source:
                    try:
                        source.write(response)
                        LOGGER.info(
                            'Stored the results of analysis %s', args.id)
                    except Exception:
                        LOGGER.error("Failed to store received ZIP.")

            except InvalidOperation as e:
                LOGGER.error('InvalidOperation: %r' % e)

    except Thrift.TException as thrift_exception:
        LOGGER.error('%s' % (thrift_exception.message))


def main():
    parser = argparse.ArgumentParser(description=".....")

    parser.add_argument('--host', type=str,
                        dest='host', default='localhost', help="...")

    parser.add_argument('--port', type=str,
                        dest='port', default='9090', help="...")

    subparsers = parser.add_subparsers(help='sub-command help')

    parser_analyze = subparsers.add_parser('analyze', help='analyze help')
    group = parser_analyze.add_mutually_exclusive_group()
    group.add_argument('-b', '--build', type=str,
                       dest='build_command', help="...")
    group.add_argument('-cdb', '--compilation_database', type=str,
                       dest='compilation_database', help="...")
    group.set_defaults(func=analyze)

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
