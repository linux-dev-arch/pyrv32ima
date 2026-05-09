<P>This project is inspired by https://github.com/Danijel-Korent/RISC-V-emulator. and https://github.com/cnlohr/mini-rv32ima
<p>
<p>This a small riscv emulator that support all instructions required to run rv32ima (NOMMU) linux written in python.
<p>WORKING:
<p>1.uart printk
<p>2.linux
<p>3.device tree
<p>4.CLINT
<p>5.Timer interrupts
<p>6.256MB of ram!
<p>
<p>TO DO:
<p>1.make code more readable
<p>2.Add uart rx to type commands
<p>3.Add terminal command line options instead of hard coded kernel and dtb files.
<p>
<p>RUN:
<p>1.clone this git repo using git
<p>2.run emulator.py with python.
<p>3.It is recommended to use pypy as it reduces boot time by a lot.
