#!/usr/bin/env python3

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import zipfile
import zlib
from contextlib import AbstractContextManager

from thrift import Thrift
from thrift.protocol import TBinaryProtocol
from thrift.transport import TSocket, TTransport

import tu_collector
from remote_analyze_api import RemoteAnalyze
from remote_analyze_api.ttypes import InvalidOperation

LOG = logging.getLogger("CLIENT")
LOG.setLevel(logging.INFO)
CH = logging.StreamHandler()
CH.setLevel(logging.INFO)
FORMATTER = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
CH.setFormatter(FORMATTER)
LOG.addHandler(CH)


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
    directory.
    """

    try:
        build_commands = {}

        if args.build_command:
            with tempfile.NamedTemporaryFile() as compilation_database:
                if args.build_command:
                    command = args.build_command
                    for part in command.split(" "):
                        if part.endswith(".cpp") or part.endswith(".c"):
                            file_path = part
                            break

                    file_path = os.path.abspath(file_path)
                    modified_command = command.replace(file_path, file_path)
                    build_commands[file_path] = modified_command
        else:
            with open(args.compilation_database) as json_file:
                compilation_database = json.load(json_file)
                LOG.debug(compilation_database)
                for item in compilation_database:
                    if "arguments" in item:
                        command = " ".join(item["arguments"])
                    else:
                        command = item["command"]
                    directory = item["directory"]
                    file_name = item["file"]

                    file_path = os.path.join(directory, file_name)

                    modified_command = command.replace(file_name, file_path)
                    build_commands[file_path] = modified_command

        LOG.debug("Build commands: %s", build_commands)

        analyzeId = None

        for file_path in build_commands:
            with tempfile.NamedTemporaryFile() as list_of_dependecies:
                command = ["python2", tu_collector.__file__]
                command.append("-b")
                command.append("%s" % build_commands[file_path])
                command.append("-ld")
                command.append("%s" % list_of_dependecies.name)

                process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                stdout, stderr = process.communicate()
                returncode = process.wait()

                LOG.debug("List temp file %s" % list_of_dependecies.name)

                files_and_hashes = {}

                with open(list_of_dependecies.name) as dependencies:
                    set_of_dependencies = json.loads(dependencies.read())

                    if args.use_cache:
                        for file_name in set_of_dependencies:
                            with open(file_name, "rb") as f:
                                file_in_bytes = f.read()
                                readable_hash = hashlib.md5(
                                    file_in_bytes).hexdigest()
                                files_and_hashes[readable_hash] = file_name

                        LOG.debug("File hashes: %s", files_and_hashes)

                        with RemoteAnalayzerClient(args.host, args.port) as client:
                            try:
                                missing_files = client.check_uploaded_files(
                                    files_and_hashes.keys()
                                )
                            except InvalidOperation as e:
                                LOG.error("InvalidOperation: %r" % e)

                        LOG.debug("Missing files: %s" % missing_files)

                        files_to_archive = {}
                        cached_files = {}

                        for hash in files_and_hashes:
                            if hash not in missing_files:
                                cached_files[hash] = files_and_hashes[hash]
                            else:
                                files_to_archive[hash] = files_and_hashes[hash]

                        LOG.info("Files need to upload: \n%s" %
                                 files_to_archive)
                        LOG.info("Files already uploaded: \n%s" % cached_files)
                    else:
                        files_to_archive = set_of_dependencies

                    with tempfile.NamedTemporaryFile(suffix=".zip") as zip_file:
                        with zipfile.ZipFile(zip_file.name, "a") as archive:
                            if files_to_archive is not None:
                                for file in files_to_archive:
                                    archive_path = os.path.join(
                                        "sources-root",
                                        files_to_archive[file].lstrip(os.sep),
                                    )

                                    try:
                                        archive.getinfo(archive_path)
                                    except KeyError:
                                        archive.write(
                                            files_to_archive[file], archive_path
                                        )
                                    else:
                                        LOG.debug(
                                            "%s is already in the ZIP file, skip it!", f
                                        )

                            archive.writestr(
                                "sources-root/build_command", build_commands[file_path]
                            )
                            archive.writestr(
                                "sources-root/file_path", file_path)
                            archive.writestr(
                                "sources-root/cached_files", json.dumps(
                                    cached_files)
                            )

                        LOG.debug("Created temporary zip file %s" %
                                  zip_file.name)

                        with RemoteAnalayzerClient(args.host, args.port) as client:
                            try:
                                if analyzeId is None:
                                    analyzeId = client.getId()
                                    LOG.info("Received id %s", analyzeId)
                            except InvalidOperation as e:
                                LOG.error("InvalidOperation: %r" % e)

                            with open(zip_file.name, "rb") as source_file:
                                file_content = source_file.read()

                                try:
                                    client.analyze(analyzeId, file_content)
                                except InvalidOperation as e:
                                    LOG.error("InvalidOperation: %r" % e)

                            LOG.info("Stored sources for id %s", analyzeId)

    except Thrift.TException as thrift_exception:
        LOG.error("%s" % (thrift_exception.message))


def get_status(args):
    """
    This method tries to get the status of the analysis from the server.
    """

    try:
        with RemoteAnalayzerClient(args.host, args.port) as client:
            try:
                response = client.getStatus(args.id)
                LOG.info("Status of analysis: %s", response)
            except InvalidOperation as e:
                LOG.error("InvalidOperation: %r" % e)

    except Thrift.TException as thrift_exception:
        LOG.error("%s" % (thrift_exception.message))


def get_results(args):
    """
    This method tries to get the results of the analysis from the server.
    """

    try:
        with RemoteAnalayzerClient(args.host, args.port) as client:
            try:
                response = client.getResults(args.id)
                with open(args.id + ".zip", "wb") as source:
                    try:
                        source.write(response)
                        LOG.info("Stored the results of analysis %s", args.id)
                    except Exception:
                        LOG.error("Failed to store received ZIP.")

            except InvalidOperation as e:
                LOG.error("InvalidOperation: %r" % e)

    except Thrift.TException as thrift_exception:
        LOG.error("%s" % (thrift_exception.message))


def main():
    parser = argparse.ArgumentParser(description=".....")

    parser.add_argument(
        "--host", type=str, dest="host", default="localhost", help="..."
    )

    parser.add_argument("--port", type=str, dest="port",
                        default="9090", help="...")

    parser.add_argument(
        "--no-cache", dest="use_cache", default=True, action="store_false"
    )

    subparsers = parser.add_subparsers(help="sub-command help")

    parser_analyze = subparsers.add_parser("analyze", help="analyze help")
    group = parser_analyze.add_mutually_exclusive_group()
    group.add_argument("-b", "--build", type=str,
                       dest="build_command", help="...")
    group.add_argument(
        "-cdb",
        "--compilation_database",
        type=str,
        dest="compilation_database",
        help="...",
    )
    group.set_defaults(func=analyze)

    parser_status = subparsers.add_parser("status", help="status help")
    parser_status.add_argument(
        "-id", "--id", type=str, dest="id", required=True, help="..."
    )
    parser_status.set_defaults(func=get_status)

    parser_results = subparsers.add_parser("results", help="results help")
    parser_results.add_argument(
        "-id", "--id", type=str, dest="id", required=True, help="..."
    )
    parser_results.set_defaults(func=get_results)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
