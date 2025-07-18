import socket
import json
from typing import Any
from config.resources import _lock

class WebServer:

    def __init__(self) -> None:
        self.__jfname="database/web_data.json"
        self.__webfname="webpage.html"
      
    def __read_json(self) -> dict[str, Any]:
        # Ensure thread safety when reading the JSON file
        with _lock:
            try:
                with open(self.__jfname, 'r') as file:
                    return json.load(file)  # type: ignore
            except FileNotFoundError:
                print(f"File {self.__jfname} not found.")
                return {}
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from {self.__jfname}: {e}")
                return {}
    
        
    def __web_page(self):
        with open(self.__webfname, 'r') as file:
            return file.read()
    
    def __update_json(self, data: dict[str, Any]) -> None:
        # Ensure thread safety when writing to the JSON file
        with _lock:
            try:
                with open(self.__jfname, 'w') as file:
                    json.dump(data, file, indent=4)  # type: ignore
            except Exception as e:
                print(f"Error writing to {self.__jfname}: {e}")

    def runner(self):
        # Create a socket server
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', 80))
        s.listen(5)

        # --------------------------------------------------------------------------

        # --------------------------------------------------------------------------

        # This section of the code will have minimum changes. 
        while True:
            conn, addr = s.accept()
            try:
                print(f"Connection from {addr}")
                request = conn.recv(1024).decode()  
                print(f"Request: {request}")
            
                # Process the request and send a response
                if "GET /" in request:
                    # Here you can handle different requests, e.g., GET, POST
                    # For simplicity, we will just return the web page
                    response = self.__web_page()
                    conn.send("HTTP/1.1 200 OK\n")
                    conn.send("Content-Type: text/html\n")
                    conn.send("Connection: close\n\n")
                    conn.sendall(response)
                elif "GET /data" in request:
                    with _lock:
                        payload = json.dumps(self.__read_json()).encode('utf-8')
                    conn.send("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n")
                    conn.send(payload)
                elif "POST /update" in request:
                    try:
                        body = request.split('\r\r\n')[-1]  # Extract after headers
                        new_data = json.loads(body)
                        self.__update_json(new_data)
                        conn.send("HTTP/1.1 200 OK\r\n\r\nUPDATED")
                    except Exception as e:
                        print("Update error:", e)
                        conn.send("HTTP/1.1 400 Bad Request\r\n\r\nBAD JSON")

                elif "POST /lock" in request:
                    if _lock.acquire(False):
                        print("Lock acquired by UI")
                        conn.send("HTTP/1.1 200 OK\r\n\r\nLOCKED")
                    else:
                        conn.send("HTTP/1.1 423 Locked\r\n\r\nALREADY LOCKED")

                elif "POST /unlock" in request:
                    try:
                        _lock.release()
                        print("Lock released by UI")
                        conn.send("HTTP/1.1 200 OK\r\n\r\nUNLOCKED")
                    except:
                        conn.send("HTTP/1.1 500 Internal Server Error\r\n\r\nFAILED")

                else:
                    conn.send("HTTP/1.1 404 Not Found\r\n\r\n")

            except Exception as e:
                print(f"Error handling request: {e}")
            finally:
                conn.close()


        


        