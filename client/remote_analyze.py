#!/usr/bin/env python3

import argparse
import hashlib
import json
import logging
import os
import sys
import subprocess
import tempfile
import zipfile
from contextlib import AbstractContextManager

from thrift import Thrift
from thrift.protocol import TBinaryProtocol
from thrift.transport import TSocket, TTransport

import tu_collector
from remote_analyze_api import RemoteAnalyze
from remote_analyze_api.ttypes import AnalysisNotFoundException
from remote_analyze_api.ttypes import AnalysisNotCompletedException

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
        compilation_commands = []

        if args.build_command:
            supported_file_extensions = {".cpp", ".c"}
            command = args.build_command
            for part in command.split(" "):
                if os.path.splitext(part)[1] in supported_file_extensions:
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
                    compilation_commands.append(item)

        LOG.debug("Build commands: %s", build_commands)
        LOG.debug("Compilation commands: %s", compilation_commands)

        analyze_id = None

        for item in compilation_commands:

            tmp = tempfile.NamedTemporaryFile()

            with open(tmp.name, 'w') as current_item:
                json.dump([item], current_item)

            with open(tmp.name) as current_item:
                with tempfile.NamedTemporaryFile() as list_of_dependecies:

                    command = ["python2", tu_collector.__file__]
                    command.append("-l")
                    command.append("%s" % current_item.name)
                    command.append("-ld")
                    command.append("%s" % list_of_dependecies.name)

                    process = subprocess.Popen(
                        command,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )

                    LOG.debug(command)

                    stdout, stderr = process.communicate()
                    returncode = process.wait()

                    LOG.debug('Standard output: %s', stdout)

                    if returncode != 0:
                        LOG.error('Error output: %s', stderr)

                    LOG.debug("List temp file %s", list_of_dependecies.name)

                    files_and_hashes = {}

                    with open(list_of_dependecies.name) as dependencies:
                        set_of_dependencies = json.load(dependencies)

                        if args.use_cache:
                            for file_name in set_of_dependencies:
                                if os.path.exists(file_name):
                                    with open(file_name, "rb") as file:
                                        file_in_bytes = file.read()
                                        readable_hash = hashlib.md5(
                                            file_in_bytes).hexdigest()
                                        files_and_hashes[readable_hash] = file_name
                                else:
                                    set_of_dependencies.remove(file_name)

                            LOG.debug("File hashes: %s", files_and_hashes)

                            with RemoteAnalayzerClient(args.host, args.port) as client:
                                missing_files = client.checkUploadedFiles(files_and_hashes.keys())
                            LOG.debug("Missing files: %s", missing_files)

                            files_to_archive = {}
                            cached_files = {}

                            for hash_value in files_and_hashes:
                                if hash_value not in missing_files:
                                    cached_files[hash_value] = files_and_hashes[hash_value]
                                else:
                                    files_to_archive[hash_value] = files_and_hashes[hash_value]

                            LOG.debug("Files need to upload: \n%s",
                                      files_to_archive)
                            LOG.debug("Files already uploaded: \n%s",
                                      cached_files)
                        else:
                            files_to_archive = set_of_dependencies

                        with tempfile.NamedTemporaryFile(suffix=".zip") as zip_file:
                            with zipfile.ZipFile(zip_file.name, "a") as archive:
                                if files_to_archive is not None:
                                    for file in files_to_archive:
                                        archive_path = os.path.join(
                                            "sources-root",
                                            files_to_archive[file].lstrip(
                                                os.sep),
                                        )

                                        try:
                                            archive.getinfo(archive_path)
                                        except KeyError:
                                            archive.write(
                                                files_to_archive[file], archive_path
                                            )
                                        else:
                                            LOG.debug(
                                                "%s is already in the ZIP file, skip it!", file
                                            )

                                set_of_path = set()
                                for dependency in set_of_dependencies:
                                    set_of_path.add(os.path.dirname(dependency))

                                archive.writestr(
                                    "sources-root/paths_of_dependencies.json",
                                    json.dumps(list(set_of_path)))

                                archive.writestr(
                                    "sources-root/compile_command.json", current_item.read())

                                archive.writestr(
                                    "sources-root/cached_files", json.dumps(
                                        cached_files)
                                )

                            LOG.debug("Created temporary zip file %s",
                                      zip_file.name)

                            with RemoteAnalayzerClient(args.host, args.port) as client:
                                analyze_id = client.getId()
                                LOG.info("Received id %s", analyze_id)

                                with open(zip_file.name, "rb") as source_file:
                                    file_content = source_file.read()

                                    client.analyze(analyze_id, file_content)

                                LOG.info("Stored sources for id %s", analyze_id)

    except Thrift.TException as thrift_exception:
        LOG.error("%s", thrift_exception.message)


def get_status(args):
    """
    This method tries to get the status of the analysis from the server.
    """

    try:
        with RemoteAnalayzerClient(args.host, args.port) as client:
            try:
                response = client.getStatus(args.id)
                LOG.info("Status of analysis: %s", response)
            except AnalysisNotFoundException:
                LOG.warning("AnalysisNotFoundException.")
                sys.exit(1)

    except Thrift.TException as thrift_exception:
        LOG.error("%s", thrift_exception.message)


def get_results(args):
    """
    This method tries to get the results of the analysis from the server.
    """

    try:
        with RemoteAnalayzerClient(args.host, args.port) as client:
            try:
                response = client.getResults(args.id)
            except AnalysisNotFoundException:
                LOG.warning("AnalysisNotFoundException.")
                sys.exit(1)
            except AnalysisNotCompletedException:
                LOG.warning("AnalysisNotCompletedException.")
                sys.exit(1)

            with open(args.id + ".zip", "wb") as source:
                try:
                    source.write(response)
                    LOG.info("Stored the results of analysis %s", args.id)
                except Exception:
                    LOG.error("Failed to store received ZIP.")

    except Thrift.TException as thrift_exception:
        LOG.error("%s", (thrift_exception.message))


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
