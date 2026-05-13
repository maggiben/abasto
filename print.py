import usb.core
import usb.util

# IDs que encontraste
dev = usb.core.find(idVendor=0x0483, idProduct=0x070b)

if dev is None:
    raise ValueError("Printer not found")

if dev.is_kernel_driver_active(0):
    dev.detach_kernel_driver(0)

dev.set_configuration()

cfg = dev.get_active_configuration()
intf = cfg[(0, 0)]

endpoint = intf[0]

data = b"\x1B\x40Hello from Python\n\x1D\x56\x00"

dev.write(endpoint.bEndpointAddress, data)
