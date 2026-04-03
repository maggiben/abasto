from escpos.printer import Usb
""" Xprinter XP-58 """
p = Usb(0x0483, 0x070b, 0, profile="XP-58")
p.text("Hello World\n")
p.barcode('1324354657687', 'EAN13', 64, 2, '', '')
p.cut()