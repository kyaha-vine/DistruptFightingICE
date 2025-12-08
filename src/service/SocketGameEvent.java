package service;

import java.io.DataInputStream;
import java.io.IOException;
import java.net.Socket;
import java.util.logging.Level;
import java.util.logging.Logger;

import protoc.MessageProto.GrpcGameEvent;
import util.SocketUtil;

public class SocketGameEvent implements Runnable {
    private Socket socket;
    private DataInputStream din;
    private boolean cancelled;

    public SocketGameEvent(Socket socket) {
        this.socket = socket;
        this.cancelled = false;
        try {
            this.din = new DataInputStream(socket.getInputStream());
        } catch (IOException e) {
            Logger.getAnonymousLogger().log(Level.SEVERE, e.getMessage());
            this.cancel();
        }
    }

    @Override
    public void run() {
        while (!cancelled && !socket.isClosed()) {
            try {
                byte[] data = SocketUtil.socketRecv(din, -1);
                GrpcGameEvent event = GrpcGameEvent.parseFrom(data);
                
                GameService.getInstance().addEvent(event);
            } catch (IOException e) {
                this.cancel();
            }
        }
    }

    public void cancel() {
        this.cancelled = true;
        try {
            if (socket != null && !socket.isClosed()) {
                socket.close();
            }
        } catch (IOException e) {
            Logger.getAnonymousLogger().log(Level.SEVERE, e.getMessage());
        }
    }
}
