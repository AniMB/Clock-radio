import socket
import json

from config.resources import _lock, json_obj


class WebServer:

    def __init__(self) -> None:
        self.__jfname="web_data.json"
        self.__webfname="./web_connectivity/webpage.html"
      
    def __read_json(self) :
        # Ensure thread safety when reading the JSON file
        with _lock:
            try:
                with open(self.__jfname, "r") as file:
                    data = json.load(file)
                    return data
            
            except Exception as e:
                print(f"Error reading from {json_obj}: {e}")
                return {}
            
    
        
    def __web_page(self):
        with open(self.__webfname, 'r') as file:
            return file.read()
    
    def __update_json(self, data) -> None:
        # Ensure thread safety when writing to the JSON file
        try:
            with open(self.__jfname, "w") as file:
                json.dump(data, file)
            print(f"JSON data written to {self.__jfname} successfully.")
        except Exception as e:
            print(f"Error writing to {data}: {e}")
    @staticmethod
    def receive_full_request(conn):
        buffer = b""
        while b"\r\n\r\n" not in buffer:
            chunk = conn.recv(1024)
            if not chunk:
                break
            buffer += chunk

        # Split header and any partial body
        header_bytes, sep, body_bytes = buffer.partition(b"\r\n\r\n")
        header_str = header_bytes.decode()

        # Extract content length
        content_length = 0
        for line in header_str.split("\r\n"):
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":")[1].strip())
                break

        # Read rest of the body
        while len(body_bytes) < content_length:
            more = conn.recv(content_length - len(body_bytes))
            if not more:
                break
            body_bytes += more

        full_request_str = (header_bytes + sep + body_bytes).decode()
        body_str = body_bytes.decode()

        return full_request_str, body_str
    def runner(self):
                

        # ---------------------------------------------------------------------------
        # Create a socket server
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', 80))
        s.listen(5)

       

        # --------------------------------------------------------------------------

        # This section of the code will have minimum changes. 
        while True:
            conn, addr = s.accept()
            try:
                print(f"Connection from {addr}")
                request, body = WebServer.receive_full_request(conn) 
                print(f"Request: {request}")
            
                # Process the request and send a response
                if "GET /data" in request:
                    
                    payload = json.dumps(self.__read_json()).encode('utf-8')
                    conn.send(f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(payload)}\r\nConnection: close\r\n\r\n".encode('utf-8'))
                    conn.sendall(payload)
                elif "GET /style.css" in request:
                    try:
                        with open("./web_connectivity/style.css", 'r') as file:
                            css_content = file.read()
                        css_bytes = css_content.encode('utf-8')
                        conn.send(f"HTTP/1.1 200 OK\r\nContent-Type: text/css\r\nContent-Length: {len(css_bytes)}\r\nConnection: close\r\n\r\n".encode('utf-8'))
                        conn.send(css_bytes)
                    except FileNotFoundError:
                        conn.send("HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n")
                elif "GET /favicon.ico" in request:
                    conn.send("HTTP/1.1 204 No Content\r\nConnection: close\r\n\r\n")
                    print("Favicon response sent.")
                elif "GET /index.js" in request:
                    try:
                        with open("./web_connectivity/index.js", 'r') as file:
                            js_content = file.read()
                        js_bytes = js_content.encode('utf-8')
                        conn.send(f"HTTP/1.1 200 OK\r\nContent-Type: application/javascript\r\nContent-Length: {len(js_bytes)}\r\nConnection: close\r\n\r\n".encode('utf-8'))
                        conn.sendall(js_bytes)
                    except FileNotFoundError:
                        conn.send("HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n")
                elif "GET /" in request:
                    # Here you can handle different requests, e.g., GET, POST
                    # For simplicity, we will just return the web page
                    response = self.__web_page()
                    response_bytes = response.encode('utf-8')
                    conn.send(f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(response_bytes)}\r\nConnection: close\r\n\r\n".encode('utf-8'))
                    conn.sendall(response_bytes)

                

                elif "POST /update" in request:
                    try:
                        body = request.split('\r\n\r\n')[-1]  # Extract after headers
                        new_data = json.loads(body)
                        self.__update_json(new_data)
                        conn.send("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\nUPDATED")
                    except Exception as e:
                        print("Update error:", e)
                        conn.send("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\nBAD JSON")

                elif "POST /lock" in request:
                    if _lock.acquire(False):
                        print("Lock acquired by UI")
                        conn.send("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\nLOCKED")
                    else:
                        conn.send("HTTP/1.1 423 Locked\r\nConnection: close\r\n\r\nALREADY LOCK")

                elif "POST /unlock" in request:
                    try:
                        _lock.release()
                        print("Lock released by UI")
                        conn.send("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\nUNLOCKED")
                    except:
                        conn.send("HTTP/1.1 500 Internal Server Error\r\nConnection: close\r\n\r\nFAILED")
                elif "POST /timeformat" in request or "POST /time_format" in request:
                    try:
                        body = request.split('\r\n\r\n')[-1]  # Extract after headers
                        new_format = json.loads(body)
                        if new_format.get("use24Hour") is not None:
                            use24Hour = new_format["use24Hour"]
                            print(f"Time format updated to {'24-hour' if use24Hour else '12-hour'}")
                            current_data = self.__read_json()
                            current_data["use24Hour"] = use24Hour
                            with _lock:
                                self.__update_json(current_data)
                            conn.send("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\nFORMAT UPDATED")
                        else:
                            conn.send("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\nINVALID FORMAT")
                    except Exception as e:
                        print("Format update error:", e)
                        conn.send("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\nBAD JSON")

                elif "POST /mute" in request:
                    try:
                        body = request.split('\r\n\r\n')[-1]  # Extract after headers
                        mute_data = json.loads(body)
                        if mute_data.get("mute") is not None:
                            mute = mute_data["mute"]
                            print(f"Mute status updated to {'muted' if mute else 'unmuted'}")
                            current_data = self.__read_json()
                            current_data["mute"] = mute
                            with _lock:
                                self.__update_json(current_data)
                            conn.send("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\nMUTE UPDATED")
                        else:
                            conn.send("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\nINVALID MUTE STATUS")
                    except Exception as e:
                        print("Mute update error:", e)
                        conn.send("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\nBAD JSON")
                elif "POST /volume" in request:
                    try:
                        body = request.split('\r\n\r\n')[-1]  # Extract after headers
                        volume_data = json.loads(body)
                        if volume_data.get("volume") is not None:
                            volume = volume_data["volume"]
                            print(f"Volume updated to {volume}")
                            current_data = self.__read_json()
                            current_data["volume"] = volume
                            with _lock:
                                self.__update_json(current_data)
                            conn.send("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\nVOLUME UPDATED")
                        else:
                            conn.send("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\nINVALID VOLUME")
                    except Exception as e:
                        print("Volume update error:", e)
                        conn.send("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\nBAD JSON")
                elif "POST /set_local_time" in request:
                    try:
                        print(request)
                        body = request.split('\r\n\r\n')[-1]  # Extract after headers
                        print(f"Received body for local time update: {body}")
                        time_data = json.loads(body)
                        if time_data["localTime"] is not None:
                            local_time = time_data["localTime"]
                            print(f"Local time updated to {local_time}")
                            current_data = self.__read_json()
                            current_data["Time"] = local_time
                            print(f"Current data before update: {current_data}")
                            with _lock:
                                self.__update_json(current_data)
                            conn.send("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\nLOCAL TIME UPDATED")
                        else:
                            conn.send("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\nINVALID TIME")
                    except Exception as e:
                        print("Local time update error:", e)
                        conn.send("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\nBAD JSON")
                elif "POST /choice" in request:
                    try:
                        body = request.split('\r\n\r\n')[-1]  # Extract after headers
                        choice_data = json.loads(body)
                        if choice_data.get("choice") is not None or choice_data.get("nowplaying") is not None:
                            choice = choice_data.get("choice", choice_data.get("nowplaying"))
                            print(f"Choice updated to {choice}")
                            current_data = self.__read_json()
                            current_data["choice"] = choice
                            with _lock:
                                self.__update_json(current_data)
                            conn.send("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\nCHOICE UPDATED")
                        else:
                            conn.send("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\nINVALID CHOICE")
                    except Exception as e:
                        print("Choice update error:", e)
                        conn.send("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\nBAD JSON")
                else:
                    conn.send("HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n")

            except Exception as e:
                print(f"Error handling request: {e}")
            finally:
                conn.close()