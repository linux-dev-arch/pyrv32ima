# pyrv32ima
This project is inspired by https://github.com/Danijel-Korent/RISC-V-emulator. and https://github.com/cnlohr/mini-rv32ima.  
pyrv32ima a small riscv emulator that support all instructions required to run rv32ima (NOMMU) linux written in python.
## WORKING:
1.uart printk  
2.linux  
3.device tree  
4.CLINT  
5.Timer interrupts  
6.256MB of ram!  
  
## TO DO:
1.make code more readable  
2.Add uart rx to type commands  
3.Add terminal command line options instead of hard coded kernel and dtb files.  
  
## RUN:
1.clone this git repo using git  
2.run emulator.py with python.  
3.It is recommended to use pypy as it reduces boot time by a lot.  
