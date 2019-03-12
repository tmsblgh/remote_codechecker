#!/usr/bin/env python3

import os
import sys
import argparse
import subprocess
import zipfile
import logging
import zlib
import tempfile
import json
import zipfile
import hashlib
import json

from contextlib import AbstractContextManager

from remote_analyze_api import RemoteAnalyze
from remote_analyze_api.ttypes import InvalidOperation

from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol

import tu_collector

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


def remove_files_from_archive(original_zip, files_to_remove):
    LOGGER.info('Remove files from the archive. [%s]' % files_to_remove)
    LOGGER.info('Old zip %s' % original_zip)
    with zipfile.ZipFile(original_zip, 'r') as zipf:
        LOGGER.info(zipf.namelist())

    with zipfile.ZipFile(original_zip, 'a') as zipf:
        with tempfile.NamedTemporaryFile(suffix='.zip') as zip_file:
            LOGGER.info('List %s' % zipf.namelist())
            for item in zipf.namelist():
                LOGGER.info('File %s' % item.filename)
                buffer = zipf.read(item.filename)
                if item.filename in files_to_remove:
                    zip_file.writestr(item, buffer)

            LOGGER.info('New zip %s' % zip_file.name)
            return zip_file.name


def analyze(args):
    """
    This method tries to collect files based on the build command for the
    remote analysis with tu_collector script to a zip file.

    If it was success it calls server's getId method to get an UUID for the
    analysis.

    Then the script saves the zip file to the workspace/{received-uuid}
    directory.
    """

    try:
        build_commands = {}

        with tempfile.NamedTemporaryFile() as compilation_database:
            if args.build_command:
                command = ["intercept-build"]
                command.append("--cdb")
                command.append("%s" % compilation_database.name)
                command.append("sh -c \"")
                command.append("%s" % args.build_command)
                command.append("\"")

                LOGGER.debug(' '.join(command))

                process = subprocess.Popen(' '.join(command),
                                           stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE,
                                           shell=True)

                # not work without shell=True ...
                # same as CC - build_manager.py:33

                stdout, stderr = process.communicate()
                returncode = process.wait()

            cdb = compilation_database.name if args.build_command else args.compilation_database

            with open(cdb) as json_file:
                compilation_database = json.load(json_file)
                LOGGER.info(compilation_database)
                for item in compilation_database:
                    command = ' '.join(item['arguments'])
                    directory = item['directory']
                    file_name = item['file']

                    file_path = os.path.join(directory, file_name)

                    modified_command = command.replace(file_name, file_path)
                    build_commands[file_path] = modified_command

        LOGGER.info('Build commands: %s', build_commands)

        analyzeId = None

        for file_path in build_commands:
            with tempfile.NamedTemporaryFile() as list_of_dependecies:
                command = ["python2", tu_collector.__file__]
                command.append("-b")
                command.append("%s" % build_commands[file_path])
                command.append("-ld")
                command.append("%s" % list_of_dependecies.name)

                process = subprocess.Popen(command,
                                        stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)

                stdout, stderr = process.communicate()
                returncode = process.wait()

                LOGGER.debug('List temp file %s' % list_of_dependecies.name)

                files_and_hashes = {}

                with open(list_of_dependecies.name) as dependencies:
                    set_of_dependencies = json.loads(dependencies.read())
                    LOGGER.info(set_of_dependencies)

                    for file_name in set_of_dependencies:
                        with open(file_name, "rb") as f:
                            bytes = f.read()
                            readable_hash = hashlib.md5(bytes).hexdigest()
                            files_and_hashes[file_name] = readable_hash

                    LOGGER.debug('File hashes: %s', files_and_hashes)

                    with RemoteAnalayzerClient(args.host, args.port) as client:
                        try:
                            list_of_missing_files = client.check_uploaded_files(files_and_hashes.values())
                        except InvalidOperation as e:
                            logger.error('InvalidOperation: %r' % e)

                    LOGGER.debug('Missing files: %s' % list_of_missing_files)

                    files_to_archive = {}
                    skipped_file_list = {}

                    for file in files_and_hashes:
                        hash = files_and_hashes[file]
                        if hash not in list_of_missing_files:
                            skipped_file_list[file] = hash
                        else:
                            files_to_archive[file] = hash

                    LOGGER.info('Files need to upload: \n%s' % files_to_archive)
                    LOGGER.info('Files already uploaded: \n%s' % skipped_file_list)

                    with tempfile.NamedTemporaryFile(suffix='.zip') as zip_file:
                        with zipfile.ZipFile(zip_file.name, 'a') as archive:
                            if files_to_archive is not None:
                                for f in files_to_archive:
                                    LOGGER.info(f)
                                    archive_path = os.path.join(
                                        'sources-root', f.lstrip(os.sep))

                                    try:
                                        archive.getinfo(archive_path)
                                    except KeyError:
                                        archive.write(f, archive_path)
                                    else:
                                        LOGGER.debug(
                                            '%s is already in the ZIP file, skip it!', f)

                            archive.writestr(
                                'sources-root/build_command', build_commands[file_path])
                            archive.writestr('sources-root/file_path', file_path)
                            archive.writestr(
                                'sources-root/skipped_file_list', json.dumps(skipped_file_list))

                        LOGGER.debug('Created temporary zip file %s' %
                                    zip_file.name)

                        with RemoteAnalayzerClient(args.host, args.port) as client:
                            try:
                                if analyzeId is None:
                                    analyzeId = client.getId()
                                    LOGGER.info('Received id %s', analyzeId)
                            except InvalidOperation as e:
                                LOGGER.error('InvalidOperation: %r' % e)

                            with open(zip_file.name, 'rb') as source_file:
                                file_content = source_file.read()

                                try:
                                    response = client.analyze(
                                        analyzeId, file_content)
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
                        LOGGER.error('Failed to store received ZIP.')

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
