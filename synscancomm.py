import socket
import logging
import os
import select

UDP_IP = os.getenv("SYNSCAN_UDP_IP","192.168.4.1")
UDP_PORT = os.getenv("SYNSCAN_UDP_PORT",11880)


class synscanComm:
    def __init__(self,udp_ip=UDP_IP,udp_port=UDP_PORT):
        logging.basicConfig(
            format='%(asctime)s %(levelname)s:synscanComm %(message)s',
            level=logging.DEBUG
            )
        logging.info(f"UDP target IP: {udp_ip}")
        logging.info(f"UDP target port: {udp_port}")
        self.sock = socket.socket(socket.AF_INET, # Internet
        socket.SOCK_DGRAM) # UDP
        self.sock.setblocking(0)
        self.udp_ip=udp_ip
        self.udp_port=udp_port
        self.commOK=False
        #self.test_comm()
    
    def send_raw_cmd(self,cmd,timeout_in_seconds=2):
        logging.debug(f"Sending cmd:{cmd}")
        self.sock.sendto(cmd,(self.udp_ip,self.udp_port))
        ready = select.select([self.sock], [], [], timeout_in_seconds)
        if ready[0]:
            self.commOK=True
            response,(fromhost,fromport) = self.sock.recvfrom(1024)
            logging.debug(f"response: {response} host:{fromhost} port:{fromport}" )
        else:
            self.commOK=False
            logging.debug(f"Socket timeout. {timeout_in_seconds}s without response" )
            raise(NameError('SynscanSocketTimeoutError'))
            response = False
        return response

    def send_cmd(self,cmd,axis,data=None):
        if data is None:
            msg=bytes(f':{cmd}{axis}\r','utf-8')
        else:
            msg=bytes(f':{cmd}{axis}{self.int2hex(data)}\r','utf-8')
        logging.debug(f'sending cmd:{msg}')
        raw_response=self.send_raw_cmd(msg)
        if raw_response[0]!=61:
            logging.warning(f'Error {raw_response[0]}. Response:{raw_response}')
            raise(NameError('SynscanCommandError'))
            return False
        response=self.hex2int(raw_response[1:-1])
        return response

    def int2hex(self,data,ndigits=6):
        assert (ndigits in [2,4,6]), "ndigits must be one of [2,4,6]"
        if ndigits==6:
            strData=f'{data:06X}'
        if ndigits==4:
            strData=f'{data:04X}'
        if ndigits==2:
            strData=f'{data:02X}'
        length=len(strData)
        logging.debug(f'Converting {data} to a synscan hex')
        strHEX=''
        for i in range(length,0,-2):
            strHEX=strHEX+f'{strData[i-2:i]}'
        logging.debug(f'{data}(decimal) => {strData}(hex) => {strHEX}(synscan hex)')
        return strHEX
        
    def hex2int(self,data):
        strData=data.decode("utf-8") 
        length=len(strData)
        assert (length<=6), f"Max allow value is FFFFFF. Actual={strData}"
        logging.debug(f'Converting {strData} to a integer')
        strHEX=''
        for i in range(length,0,-2):
            strHEX=strHEX+f'{strData[i-2:i]}'
        if length==0:
            return ''
        else:
            v=int(strHEX,16)
            logging.debug(f'{strData}(synscan hex) => {strHEX}(hex) => {v}(decimal)')
            return v

    def test_comm(self):
        MESSAGE = b":F3\r"
        logging.info(f"Testing comms. Asking if initialized..")
        response=self.send_raw_cmd(MESSAGE)
        
        if response == b'=\r':
            logging.info(f"Mount initialized. Connection OK" )
        else:
            logging.info(f"Mount not initialized. Connection FAIL" )

if __name__ == '__main__':
    smc=synscanComm()
    smc.int2hex(smc.hex2int(b'1FCA89'))
    smc.int2hex(smc.hex2int(b'5F3A'),4)
    smc.int2hex(smc.hex2int(b'B8'),2)


