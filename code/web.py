import socket
class Website:
    def __init__(self,json_filename:str, webpage:str) -> None:
        self.__jfname=json_filename
        self.__web=webpage
    
    def __web_page(self):
        pass
    
    def __get_status(self):
        pass

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
                request = str(request)
                print('Content = %s' % request)
              


           


            # this part of the code remains as it is. 

            if request.find("/status") == 6:
                response = self.__get_status()
                conn.send("HTTP/1.1 200 OK\n")
                conn.send("Content-Type: application/json\n")
                conn.send("Connection: close\n\n")
                conn.sendall(response)

            else:
                response = self.__web_page()
                conn.send("HTTP/1.1 200 OK\n")
                conn.send("Content-Type: text/html\n")
                conn.send("Connection: close\n\n")
                conn.sendall(response)
            conn.close()

        