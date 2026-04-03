import argparse

import usb.core
import usb.util

VENDOR_ID = 0x0483
PRODUCT_ID = 0x070b

dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
dev.set_configuration()

cfg = dev.get_active_configuration()
intf = cfg[(0, 0)]
endpoint = intf[0]

def send(data):
    dev.write(endpoint.bEndpointAddress, data)

def print_code128(data_str):
    data = data_str.encode("ascii")

    send(b'\x1B\x40')           # init
    send(b'\x1B\x61\x01')       # center

    send(b'\x1D\x68\x64')       # altura
    send(b'\x1D\x77\x02')       # ancho
    send(b'\x1D\x48\x02')       # texto debajo

    # CODE128 requiere prefijo {B
    send(b'\x1D\x6B\x49' + bytes([len(data)+2]) + b'{B' + data)

    send(b'\n\n\n')
    send(b'\x1D\x56\x00')


def main():
    parser = argparse.ArgumentParser(description="Print a CODE128 barcode on the USB label printer.")
    parser.add_argument("text", help="String to encode (ASCII)")
    args = parser.parse_args()
    print_code128(args.text)


if __name__ == "__main__":
    main()