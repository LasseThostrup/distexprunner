import threading
import logging
import xmlrpc.client
import subprocess
import time
import shlex

from utils import LinePipe


class ServerProcess(threading.Thread):
    def __init__(self, id, cmd, callback_addr):
        super().__init__()
        self.id = id
        self.cmd = cmd
        self.callback_addr = callback_addr
        self.rc = None
        self.p = None

        self.daemon = False
        self.start()

    def cmd_stdout(self, l):
        try:
            with xmlrpc.client.ServerProxy(self.callback_addr) as proxy:
                proxy.cmd_stdout(self.id, l)
        except ConnectionRefusedError:
            pass

    def cmd_stderr(self, l):
        try:
            with xmlrpc.client.ServerProxy(self.callback_addr) as proxy:
                proxy.cmd_stderr(self.id, l)
        except ConnectionRefusedError:
            pass
    
    def run(self):
        logging.info(f'Running cmd: {self.cmd}')
        stdout = LinePipe(callback=self.cmd_stdout) #TODO change to partial
        stderr = LinePipe(callback=self.cmd_stderr)
        self.p = subprocess.Popen(shlex.split(self.cmd), stdout=stdout, stderr=stderr, stdin=subprocess.PIPE, bufsize=0, shell=False)

        self.p.wait()
        self.rc = self.p.returncode
        logging.info(f'Cmd {self.id} ({self.cmd}) exited with: {self.p.returncode}')

        try:
            with xmlrpc.client.ServerProxy(self.callback_addr) as proxy:
                proxy.cmd_rc(self.id, self.p.returncode)
        except ConnectionRefusedError:
            pass

        stdout.close()
        stderr.close()

    def stdin(self, line):
        if self.rc:
            raise Exception(f'Process alreading terminated could not send stdin: {line}')

        self.__wait_for_p()
        self.p.stdin.write(line)
        self.p.stdin.flush()


    def kill(self):
        if self.rc:
            return

        self.__wait_for_p()
        self.p.kill()
        self.p.wait()


    def __wait_for_p(self):
        while self.p is None:   # TODO better solution, wait for unstarted process
            time.sleep(0.01)


    def cleanup(self):
        self.kill()
