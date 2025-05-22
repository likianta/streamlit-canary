import os
import streamlit_canary as sc
print(os.getpid())
# os.environ['SC_PID_TO_PORT_3001'] = str(os.getpid())
sc.run('test/button_to_close_window_slave.py', 3001, show_window=True)
