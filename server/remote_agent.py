#!/usr/bin/env python3

"""
Server for handling remote analyze requests with CodeChecker.
"""

from __future__ import print_function

import os
import sys
import uuid
import subprocess
import zipfile
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

sys.path.append('../gen-py')
from remote_analyze_api import RemoteAnalyze


class RemoteAnalyzeHandler:
    def analyze(self, command, zip_file):
        print('Starting analyze...')

        random_uuid = str(uuid.uuid4())

        run_zip_file = random_uuid + '.zip'

        try:
            with open(run_zip_file, 'wb') as zipf:
                zipf.write(zip_file)
        except IOError:
            print("Failed to extract received ZIP.")

        path = str(random_uuid) + '/'

        with zipfile.ZipFile(run_zip_file) as zf:
            zf.extractall(path)

        file_name = command.rsplit(' ', 1)[1]

        run_command = command.rsplit(' ', 1)[0]

        for root, directories, files in os.walk(path):
            for directory in directories:
                os.chmod(os.path.join(root, directory), 0o744)
            for file in files:
                os.chmod(os.path.join(root, file), 0o744)
                if file == file_name:
                    file_path = os.path.join(root, file)

        command = ["CodeChecker", "check"]
        command.append("-b")
        command.append("%s %s" % (run_command, file_path))
        command.append("-o")
        command.append("%s" % (os.path.join(random_uuid, 'output')))

        process = subprocess.Popen(command,
                                   stdout=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)

        output, err = process.communicate()
        p_status = process.wait()

        print("Command output: \n%s" % output)
        print("Error output: %s" % err)
        print("Return code: %s" % p_status)

        output = zipfile.ZipFile(random_uuid + '_output.zip', 'w')
        for root, dirs, files in os.walk(os.path.join(random_uuid, 'output')):
            for file in files:
                output.write(os.path.join(root, file))
        output.close()

        output_file = open(random_uuid + '_output.zip', 'rb')
        response = output_file.read()
        output_file.close()

        return response


if __name__ == '__main__':
    HANDLER = RemoteAnalyzeHandler()
    PROCESSOR = RemoteAnalyze.Processor(HANDLER)
    TRANSPORT = TSocket.TServerSocket(host='0.0.0.0', port=9090)
    T_FACTORY = TTransport.TBufferedTransportFactory()
    P_FACTORY = TBinaryProtocol.TBinaryProtocolFactory()

    SERVER = TServer.TSimpleServer(PROCESSOR, TRANSPORT, T_FACTORY, P_FACTORY)

    print('Starting the server...')
    SERVER.serve()
    print('Server stopped.')
