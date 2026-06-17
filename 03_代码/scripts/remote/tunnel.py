"""SSH 本地端口转发:本机 localhost:8001 -> 远端 localhost:8000(vLLM server)。

本机不能直连 ssh,用 paramiko 的 direct-tcpip 通道实现 `ssh -L`。
前台阻塞运行(供后台进程跑),Ctrl-C / 杀进程即关闭。
本地 run_eval 把 ApiLLM base_url 指向 http://localhost:8001/v1 即可访问远端模型。
"""

import select
import socketserver
import sys

import paramiko

from probe_gpu import HOST, PASSWORD, PORT, USER

LOCAL_PORT = 8001
REMOTE_HOST = "127.0.0.1"
REMOTE_PORT = 8000


class Handler(socketserver.BaseRequestHandler):
    ssh_transport = None

    def handle(self):
        try:
            chan = self.ssh_transport.open_channel(
                "direct-tcpip", (REMOTE_HOST, REMOTE_PORT), self.request.getpeername()
            )
        except Exception as e:
            print(f"转发开通失败: {e}")
            return
        if chan is None:
            return
        while True:
            r, _, _ = select.select([self.request, chan], [], [])
            if self.request in r:
                data = self.request.recv(16384)
                if len(data) == 0:
                    break
                chan.sendall(data)
            if chan in r:
                data = chan.recv(16384)
                if len(data) == 0:
                    break
                self.request.sendall(data)
        chan.close()
        self.request.close()


class ForwardServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    transport = client.get_transport()
    transport.set_keepalive(30)
    Handler.ssh_transport = transport
    print(f"隧道就绪: localhost:{LOCAL_PORT} -> {HOST}:远端 {REMOTE_PORT}。Ctrl-C 关闭。")
    sys.stdout.flush()
    server = ForwardServer(("127.0.0.1", LOCAL_PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
