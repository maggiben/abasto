const escpos = require('escpos');
escpos.USB = require('escpos-usb');

console.log(escpos.USB.findPrinter());
const device = new escpos.USB(0x0483, 0x070b); // (esto lo ajustamos abajo)
const printer = new escpos.Printer(device);

device.open((err) => {
  if (err) {
    console.error("Open error:", err);
    return;
  }

  printer
    .hardware('init')
    .align('CT')
    .text('XP-58 OK')
    .text('Impresion directa USB')
    .cut()
    .close();
});