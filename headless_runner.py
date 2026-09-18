import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addon

server = addon.get_server()
server.start()
while server.running:
    server.pump()
    time.sleep(0.05)
print("[runner] exited")
