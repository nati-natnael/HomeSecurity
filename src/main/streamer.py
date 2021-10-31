import cv2
import zmq

from time import sleep

IP = "192.168.0.7"
PORT = "5555"

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.connect("tcp://" + IP + ":" + PORT)

print("Streamer started at port" + PORT)

camera = cv2.VideoCapture(0)

while True:
    try:
        grabbed, frame = camera.read()
        frame = cv2.resize(frame, (480, 320))
        
        encoded, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        socket.send(buffer)

        sleep(0.0005)

    except KeyboardInterrupt:
        camera.release()
        cv2.destroyAllWindows()
        break
