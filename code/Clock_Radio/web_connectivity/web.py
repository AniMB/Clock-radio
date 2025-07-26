import socket
import json

from config.resources import _lock


class WebServer:

    def __init__(self) -> None:
        self.__jfname="web_data.json"
        self.__webfname="./web_connectivity/webpage.html"
      
    def __read_json(self) :
        # Ensure thread safety when reading the JSON file
        if _lock.acquire(blocking=False):
            try:
                with open(self.__jfname, 'r') as file:
                    return json.load(file)  # type: ignore
            except FileNotFoundError:
                print(f"File {self.__jfname} not found.")
                return {}
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from {self.__jfname}: {e}")
                return {}
            finally:
                _lock.release()
        else:
            print("Lock is already acquired, cannot read JSON file.")
            return {}
    
        
    def __web_page(self):
        with open(self.__webfname, 'r') as file:
            return file.read()
    
    def __update_json(self, data) -> None:
        # Ensure thread safety when writing to the JSON file
        try:
            with open(self.__jfname, 'w') as file:
                json.dump(data, file, indent=4)  # type: ignore
        except Exception as e:
            print(f"Error writing to {self.__jfname}: {e}")

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
                request = conn.recv(1024).decode()  
                print(f"Request: {request}")
            
                # Process the request and send a response
                if "GET /data" in request:
                    
                    payload = json.dumps(self.__read_json()).encode('utf-8')
                    conn.send("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n")
                    conn.send(payload)
                elif "GET /style.css" in request:
                    try:
                        with open("./web_connectivity/style.css", 'r') as file:
                            css_content = file.read()
                        conn.send("HTTP/1.1 200 OK\r\nContent-Type: text/css\r\nConnection: close\r\n\r\n")
                        conn.send(css_content.encode('utf-8'))
                    except FileNotFoundError:
                        conn.send("HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n")
                elif "GET /favicon.ico" in request:
                    conn.send("HTTP/1.1 204 No Content\r\nConnection: close\r\n\r\n")
                    print("Favicon response sent.")
                elif "GET /index.js" in request or "GET index.js" in request:
                    try:
                        with open("./web_connectivity/index.js", 'r') as file:
                            js_content = file.read()
                        conn.send("HTTP/1.1 200 OK\r\nContent-Type: application/javascript\r\nConnection: close\r\n\r\n")
                        conn.sendall(js_content.encode('utf-8'))
                    except FileNotFoundError:
                        conn.send("HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n")
                elif "GET /" in request:
                    # Here you can handle different requests, e.g., GET, POST
                    # For simplicity, we will just return the web page
                    response = self.__web_page()
                    conn.send("HTTP/1.1 200 OK\r\n")
                    conn.send("Content-Type: text/html\r\n")
                    conn.send("Connection: close\r\n\r\n")
                    conn.sendall(response.encode('utf-8'))

                

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
                    if _lock.acquire(blocking=False):
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
                elif "POST /timeformat" in request:
                    try:
                        body = request.split('\r\r\n')[-1]  # Extract after headers
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
                        body = request.split('\r\r\n')[-1]  # Extract after headers
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
                        body = request.split('\r\r\n')[-1]  # Extract after headers
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
                        body = request.split('\r\r\n')[-1]  # Extract after headers
                        time_data = json.loads(body)
                        if time_data.get("localTime") is not None:
                            local_time = time_data["localTime"]
                            print(f"Local time updated to {local_time}")
                            current_data = self.__read_json()
                            current_data["Time"] = local_time
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
                        body = request.split('\r\r\n')[-1]  # Extract after headers
                        choice_data = json.loads(body)
                        if choice_data.get("choice") is not None:
                            choice = choice_data["choice"]
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