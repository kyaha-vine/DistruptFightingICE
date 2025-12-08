import socket
import struct
import message_pb2
import time
import tkinter as tk
import random

class EventInjectorGUI:
    def __init__(self, master):
        self.master = master
        master.title("Event Injector")
        # "hight width maybe 300 400" -> Interpreting as Height=300, Width=400
        master.geometry("400x300") 
        
        self.canvas = tk.Canvas(master, width=400, height=300, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        self.sock = None
        self.connect_socket()
        
        self.current_event_id = 0
        self.is_dragging = False
        self.current_x = 0
        self.current_y = 0
        self.vx = 0
        self.vy = 0
        
    def connect_socket(self):
        try:
            if self.sock:
                self.sock.close()
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(('127.0.0.1', 31415))
            # 1. Send Role (6 = Game Event Injector)
            self.sock.send(b'\x06')
            print("Connected to game server.")
        except Exception as e:
            print(f"Connection failed: {e}")
            self.sock = None

    def send_event(self, event_type, terminate):
        if self.sock is None:
            # Try to reconnect once
            self.connect_socket()
            if self.sock is None:
                return

        try:
            event = message_pb2.GrpcGameEvent()
            event.event_id = self.current_event_id
            event.event_type = event_type
            event.x = self.current_x
            event.y = self.current_y
            event.vx = self.vx
            event.vy = self.vy
            event.time = 180
            event.terminate = terminate
            
            data = event.SerializeToString()
            self.sock.send(struct.pack('<I', len(data)))
            self.sock.send(data)
            print(f"Sent: ID={event.event_id}, Type={event.event_type}, X={event.x}, Y={event.y}, Term={event.terminate}")
        except Exception as e:
            print(f"Send failed: {e}")
            self.sock = None

    def on_press(self, event):
        self.is_dragging = True
        self.current_x = event.x
        self.current_y = event.y
        self.vx = 0
        self.vy = 0
        self.send_loop()

    def on_drag(self, event):
        # Calculate speed based on mouse movement
        dx = event.x - self.current_x
        dy = event.y - self.current_y
        
        # Clamp speed between -3 and 3
        self.vx = max(-3, min(3, dx))
        self.vy = max(-3, min(3, dy))
        
        self.current_x = event.x
        self.current_y = event.y

    def on_release(self, event):
        self.is_dragging = False
        self.current_x = event.x
        self.current_y = event.y
        # Send final terminate message
        self.send_event(event_type=1, terminate=True)
        self.current_event_id += 1

    def send_loop(self):
        if self.is_dragging:
            self.send_event(event_type=0, terminate=False)
            # 30 Hz is approx 33ms
            self.master.after(33, self.send_loop)

if __name__ == "__main__":
    root = tk.Tk()
    gui = EventInjectorGUI(root)
    root.mainloop()
