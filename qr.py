import usb.core
import usb.util

# IDs que encontraste
VENDOR_ID = 0x0483
PRODUCT_ID = 0x070b

dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

if dev is None:
    raise ValueError("Printer not found")

if dev.is_kernel_driver_active(0):
    dev.detach_kernel_driver(0)

dev.set_configuration()

cfg = dev.get_active_configuration()
intf = cfg[(0, 0)]
endpoint = intf[0]

def send(data):
    dev.write(endpoint.bEndpointAddress, data)

def print_qr(data_str):
    data = data_str.encode("utf-8")
    length = len(data) + 3
    pL = length % 256
    pH = length // 256

    # INIT
    send(b'\x1B\x40')

    # Center align
    send(b'\x1B\x61\x01')

    # Set QR size (1–16)
    send(b'\x1D\x28\x6B\x03\x00\x31\x43\x06')

    # Set error correction (48–51 => L, M, Q, H)
    send(b'\x1D\x28\x6B\x03\x00\x31\x45\x30')

    # Store data in QR
    send(b'\x1D\x28\x6B' + bytes([pL, pH]) + b'\x31\x50\x30' + data)

    # Print QR
    send(b'\x1D\x28\x6B\x03\x00\x31\x51\x30')

    # Feed + cut
    send(b'\n\n\n')
    send(b'\x1D\x56\x00')


# 🔥 TEST
print_qr("https://picto-cripto.com")