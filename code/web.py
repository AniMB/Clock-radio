import socket
import json
from typing import Any
from resources import _lock

class Website:

    def __init__(self,json_filename:str, webpage_fname:str) -> None:
        self.__jfname=json_filename
        self.__webfname=webpage_fname
      

        
    def __web_page(self):
        with open(self.__webfname, 'r') as file:
            return file.read()
    
    def __add_json(self,content:dict[str,Any] )->bool:
        # Ensure thread safety when writing to the JSON file
        with _lock:
            try:
                with open(self.__jfname, 'w') as file:
                    json.dump(content, file, indent=4) # type: ignore
                return True
            except Exception as e:
                print(f"Error writing to JSON file: {e}")
                return False

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
            print('Got a connection from %s' % str(addr))
            request = conn.recv(1024)
            if request:
                json_str = request.decode()      
                json_obj = json.loads(json_str)
                self.__add_json(json_obj)  
                request=b''

            # Process the request and send a response
          
            response = self.__web_page()
            conn.send("HTTP/1.1 200 OK\n")
            conn.send("Content-Type: text/html\n")
            conn.send("Connection: close\n\n")
            conn.sendall(response)
            conn.close()


        


        