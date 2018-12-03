#!/usr/bin/env python3

import os
import sys
sys.path.append('../gen-py')

import uuid
import zlib
import logging
import subprocess
import tempfile
import zipfile

from remote_analyze_api import RemoteAnalyze
from remote_analyze_api.ttypes import InvalidOperation

from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

logger = logging.getLogger('SERVER')
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


class RemoteAnalyzeHandler:
    def __init__(self):
        self.log = {}

    def analyze(self, command, zip_file):
        logger.info('Analyze')

        random_uuid = str(uuid.uuid4())

        run_zip_file = random_uuid + '.zip'

        with open(run_zip_file, 'wb') as zipf:
            try:
                zipf.write(zip_file)
            except Exception:
                logger.error("Failed to extract received ZIP.")

        path = str(random_uuid) + '/'

        with zipfile.ZipFile(run_zip_file) as zf:
            zf.extractall(path)

        file_name = command.rsplit(' ', 1)[1]

        run_command = command.rsplit(' ', 1)[0]

        ###
        for root, dirs, files in os.walk(path):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o744)
            for f in files:
                os.chmod(os.path.join(root, f), 0o744)
                if f == file_name:
                    file_path = os.path.join(root, f)

        command = "~/codechecker/build/CodeChecker/bin/CodeChecker check -b \"%s %s\" -o %s" % (
            run_command, file_path, os.path.join(random_uuid, 'output'))
        logger.info("Command        : %s" % command)

        process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        output, err = process.communicate()
        p_status = process.wait()

        logger.info("Command output : \n%s" % output)
        logger.debug("Error output   : %s" % err)
        logger.debug("Return code    : %s" % p_status)

        output = zipfile.ZipFile(random_uuid + '_output.zip', 'w')
        for root, dirs, files in os.walk(os.path.join(random_uuid, 'output')):
            for f in files:
                output.write(os.path.join(root, f))
        output.close()

        f = open(random_uuid + '_output.zip', 'rb')
        response = f.read()
        f.close()

        return response


if __name__ == '__main__':
    handler = RemoteAnalyzeHandler()
    processor = RemoteAnalyze.Processor(handler)
    transport = TSocket.TServerSocket(host='127.0.0.1', port=9090)
    tfactory = TTransport.TBufferedTransportFactory()
    pfactory = TBinaryProtocol.TBinaryProtocolFactory()

    server = TServer.TSimpleServer(processor, transport, tfactory, pfactory)

    print('Starting the server...')
    server.serve()
    print('done.')
