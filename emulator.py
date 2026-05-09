import sys,time,platform,msvcrt

ram=bytearray(1024*1024*128)
csrs=[0]*4096
with open("linux_image","rb")as f:
    linux_image=f.read()

with open("dtb_image","rb")as f:
    dtb_image=f.read()
ram_base=0x80000000
dtb_addr=0x803A0d10
clint_time=0
regs=[0]*32
regs[11]=dtb_addr#0x87FF0000
pc=0x80000000
mtimecmp_bytes=bytearray(b'\xff' * 8)
#regs[2] = 0x87F00000
reservation=None
uart_rx_buf=[]
def get_mtimecmp():
    return int.from_bytes(mtimecmp_bytes, 'little')
def device_clint(address):
    global clint_time
    if address == 0x1100BFF8:
        return clint_time & 0xff
    elif address == 0x1100BFF9:
        return (clint_time >> 8)&0xff
    elif address == 0x1100BFFA:
        return (clint_time >> 16)&0xff
    elif address == 0x1100BFFB:
        return (clint_time >> 24)&0xff
    elif address == 0x1100BFFC:
        return (clint_time >> 32)&0xff
    elif address == 0x1100BFFD:
        return (clint_time >> 40)&0xff
    elif address == 0x1100BFFE:
        return (clint_time >> 48)&0xff
    elif address == 0x1100BFFF:
        return (clint_time >> 56)&0xff
    else:
        raise Exception("Attempted to read unimplemented CLINT register")
def get_byte(addr):
    if addr>=ram_base:
        return ram[addr-ram_base]
    elif addr >= 0x10000000 and addr <= 0x10000008:
        if addr==0x10000005:
            return 0x60  # no data
        if addr == 0x10000000:
            return 0
        return 0
    elif addr >=0x1100BFF8 and addr <=0x1100BFFF:
        return device_clint(addr)
    elif addr >= 0x11004000 and addr <= 0x11004007:
        return mtimecmp_bytes[addr - 0x11004000]
    else:
        return 0;
def write_byte(addr,value):
    global mtimecmp_bytes
    if addr>=ram_base:
         ram[addr-ram_base] = value
    elif addr == 0x10000000:
        print(chr(value),end="",flush=True)
    elif addr >= 0x11004000 and addr <= 0x11004007:
        mtimecmp_bytes[addr - 0x11004000] = value & 0xff
def write_2_bytes(addr,value):
    write_byte(addr,value&0xFF)
    write_byte(addr+1,(value >> 8)&0xff)
def write_4_bytes(addr,value):
    write_byte(addr,value&0xFF)
    write_byte(addr+1,(value >> 8)&0xff)
    write_byte(addr+2,(value >> 16)&0xff)
    write_byte(addr+3,(value >> 24)&0xff)
def sign_extend(val, bits):
    if val & (1 << (bits - 1)):
        val -= (1 << bits)
    return val
def load_image(addr,image):
    print("loaded at:",hex(addr))
    addr -= ram_base
    for i in range(len(image)):
        if ram[addr+i] ==0:
            ram[addr+i]=image[i]#load at ram offset
        else:
            print("overwriting memory!!!")
            break

def get_instr(addr):
    return get_byte(addr)+(get_byte(addr+1)<<8)+(get_byte(addr+2)<<16)+(get_byte(addr+3)<<24)

def get_4_bytes(addr):
    return get_byte(addr)+(get_byte(addr+1)<<8)+(get_byte(addr+2)<<16)+(get_byte(addr+3)<<24)

def get_opcode(instr):
    return instr&0x7f

def get_rd(instr):
    return (instr& 0xf80)>>7

def get_imm_j(instr):
    imm20    = (instr >> 31) & 0x1
    # instruction[30:21] -> imm[10:1]
    imm10_1  = (instr>> 21) & 0x3FF
    # instruction[20] -> imm[11]
    imm11    = (instr>> 20) & 0x1
    # instruction[19:12] -> imm[19:12]
    imm19_12 = (instr>> 12) & 0xFF

    # Reassemble bits into the 21-bit final immediate (with the implied 0)
    # Result structure: [imm20][imm19_12][imm11][imm10_1][0]
    imm = (imm20 << 20) | (imm19_12 << 12) | (imm11 << 11) | (imm10_1 << 1)
    return sign_extend(imm,21)

def get_funct3(instr):
    return (instr & 0x7000)>> 12

def get_funct5(instr):
    return (instr >> 27) & 0x1F

def get_rs1(instr):
    return (instr  >> 15) & 0x1f

def get_rs2(instr):
    return (instr >> 20 ) &0x1f

def get_imm_i(instr):
    imm = (instr >> 20)&0xfff
    return sign_extend(imm,12)
def get_imm_u(instr):
    return ((instr  >> 12 ) & 0xFFFFF)

def get_funct7(instr):
    return (instr >> 25) &0x7f
def get_imm_b(instr):
    imm_12   = (instr >> 31) & 0x01
    imm_11   = (instr >> 7)  & 0x01
    imm_10_5 = (instr >> 25) & 0x3F
    imm_4_1  = (instr >> 8)  & 0x0F

    return sign_extend((imm_12 << 12) | (imm_11 << 11) | (imm_10_5 << 5) | (imm_4_1 << 1),13)

def get_imm_s(instr):
    imm_11_5 = (instr >> 25) & 0x7F
    imm_4_0 = (instr >> 7) & 0x1F
    # Combine immediate bits and sign-extend to 32-bit
    imm = (imm_11_5 << 5) | imm_4_0
    return sign_extend(imm,12)
def get_mtimecmp():
    return int.from_bytes(mtimecmp_bytes, 'little')
def cpu_step(instr):
    global pc,ram,regs,debug,reservation
    regs[0]=0
    opcode=get_opcode(instr)
    if count%10==0 and debug==True:
        print(hex(instr),hex(opcode),hex(pc))
    if opcode==0x6f:
        #jal
        rd = get_rd(instr)
        imm=get_imm_j(instr)
        regs[rd]=(pc+4)&0xFFFFFFFF
        pc=pc+imm
    elif opcode==0x73:
        funct3 =get_funct3(instr)
        if funct3 == 1:
            #csrrw _NOTE:imm is csr
            imm = get_imm_i(instr)
            rs1 = get_rs1(instr)
            rd = get_rd(instr)
            t = csrs[imm] & 0xffffffff
            csrs[imm]=regs[rs1]
            regs[rd]=t
            pc+=4
        elif funct3 == 5:
            #csrrwi
            csr = get_imm_i(instr)
            rd = get_rd(instr)
            imm = get_rs1(instr)#same bits as rs1
            t=csrs[csr] & 0xffffffff
            csrs[csr]=imm
            regs[rd]=t
            pc+=4
        elif funct3 == 2:
            #csrrs
            imm = get_imm_i(instr)
            rs1 = get_rs1(instr)
            rd = get_rd(instr)
            t = csrs[imm] & 0xffffffff
            regs[rd]=t
            csrs[imm] = t | regs[rs1]
            pc+=4
        elif funct3 == 3:
            #csrrc
            imm = get_imm_i(instr)
            rs1 = get_rs1(instr)
            rd = get_rd(instr)
            t = csrs[imm] &0xffffffff
            regs[rd]=t
            csrs[imm] = t & ~regs[rs1]
            pc+=4
        elif funct3 == 7:
            #csrrci
            csr = get_imm_i(instr)
            zimm = get_rs1(instr)
            rd = get_rd(instr)
            t = csrs[csr] &0xffffffff
            regs[rd]=t
            csrs[csr] = t & ~zimm
            pc+=4
        elif funct3 == 6:
            #csrrsi
            csr = get_imm_i(instr)
            zimm = get_rs1(instr)
            rd = get_rd(instr)
            t = csrs[csr] &0xffffffff
            if (zimm !=0):
                csrs[csr] = t|zimm
            regs[rd]=t
            pc+=4
        elif funct3 == 0:
            if instr == 0x30200073:
                #mret
                pc=csrs[0x341] & 0xffffffff
                mpie = (csrs[0x300] >> 7) & 1
                csrs[0x300] = (csrs[0x300] & ~0x8) | (mpie << 3)
                csrs[0x300] |= (1<<7)
            elif instr==0x10500073:
                #wfi
                pc=pc+4
            else:
                # ecall
                csrs[0x341] = pc
                csrs[0x342] = 8
                old_mie = (csrs[0x300] >> 3) & 1
                csrs[0x300] = (csrs[0x300] & ~(1 << 7)) | (old_mie << 7)  # MPIE = old MIE
                csrs[0x300] &= ~0x8
                pc = csrs[0x305] & ~3
    elif opcode==0xf:
        funct3=get_funct3(instr)
        if funct3 == 1:
            #fence.i
            pc+=4
        elif funct3 == 0:
            pc+=4

    elif opcode == 0x13:
        funct3 = get_funct3(instr)
        funct7 = get_funct7(instr)
        if funct3 ==0:
            imm = get_imm_i(instr)
            rs1 = get_rs1(instr)
            rd = get_rd(instr)
            regs[rd]=(regs[rs1]+imm )& 0xffffffff
            pc+=4
        elif funct3 == 7:
            imm = get_imm_i(instr)
            rs1 = get_rs1(instr)
            rd = get_rd(instr)
            regs[rd]=(regs[rs1]&imm)&0xffffffff
            pc+=4
        elif funct3 == 4:
            imm = get_imm_i(instr)
            rs1 = get_rs1(instr)
            rd = get_rd(instr)
            regs[rd]=(regs[rs1]^imm)&0xffffffff
            pc+=4
        elif funct3 == 6:
            imm = get_imm_i(instr)
            rs1 = get_rs1(instr)
            rd = get_rd(instr)
            regs[rd]=(regs[rs1]|imm)&0xffffffff
            pc+=4
        elif funct3==1:
            if funct7 == 0:
                rs1=get_rs1(instr)
                rd = get_rd(instr)
                shamt = (instr >> 20) & 0x1F
                regs[rd]=(regs[rs1] << shamt) & 0xffffffff
                pc+=4
        elif funct3==5 and funct7==0x20:
            #srai
            rs1=get_rs1(instr)
            rd = get_rd(instr)
            shamt = (instr >> 20) & 0x1F
            v=sign_extend(regs[rs1]&0xffffffff,32)
            regs[rd] = (v >> shamt) & 0xffffffff
            pc+=4
        elif funct3==5 and funct7==0x0:
            #srli
            rs1=get_rs1(instr)
            rd = get_rd(instr)
            shamt = (instr >> 20) & 0x1F
            v=regs[rs1]&0xffffffff
            regs[rd] = (v >> shamt) & 0xffffffff
            pc+=4
        elif funct3==3:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            imm = get_imm_i(instr)
            v1 = regs[rs1] & 0xffffffff
            v2 = imm&0xffffffff
            if v1 < v2:
                regs[rd] = 1
            else:
                regs[rd] = 0
            pc+=4
        elif funct3==2:
            #slti
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            imm = get_imm_i(instr)
            v1 = sign_extend(regs[rs1] & 0xffffffff,32)
            v2 = imm
            if v1 < v2:
                regs[rd] = 1
            else:
                regs[rd] = 0
            pc+=4
    elif opcode==0x67:
        funct3=get_funct3(instr)
        if funct3 == 0:
            #jalr
            imm = get_imm_i(instr)
            rs1 = get_rs1(instr)
            rd = get_rd(instr)
            t=(pc+4)&0xffffffff
            pc = ((imm + regs[rs1])&0xffffffff)
            pc = pc & ~1
            regs[rd] = t
    elif opcode == 0x17:
        rd = get_rd(instr)
        imm = get_imm_u(instr)
        regs[rd] =(pc+(imm << 12)) & 0xffffffff
        pc+=4
    elif opcode == 0x37:
        rd = get_rd(instr)
        imm = get_imm_u(instr)
        regs[rd] = (imm << 12)& 0xffffffff
        pc+=4
    elif opcode == 0x63:
        funct3 = get_funct3(instr)
        if funct3 == 4:
            #blt
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            imm = get_imm_b(instr)
            v1 = sign_extend(regs[rs1] & 0xFFFFFFFF, 32)
            v2 = sign_extend(regs[rs2] & 0xFFFFFFFF, 32)
            if v1 < v2:
                pc = pc + imm
            else:
                pc += 4
        elif funct3 == 5:
            #bge
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            imm = get_imm_b(instr)
            v1 = sign_extend(regs[rs1] & 0xFFFFFFFF, 32)
            v2 = sign_extend(regs[rs2] & 0xFFFFFFFF, 32)

            if v1 >= v2:
                pc = pc + imm
            else:
                pc += 4
        elif funct3 == 7:
            #bgeu
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            imm = get_imm_b(instr)
            v1 = regs[rs1] & 0xFFFFFFFF
            v2 = regs[rs2] & 0xFFFFFFFF

            if v1 >= v2:
                pc = pc + imm
            else:
                pc += 4
        elif funct3 == 1:
            #bne
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            imm = get_imm_b(instr)
            v1 = (regs[rs1] & 0xFFFFFFFF)
            v2 = (regs[rs2] & 0xFFFFFFFF)

            if v1 != v2:
                pc = pc + imm
            else:
                pc += 4
        elif funct3 == 0:
            #beq
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            imm = get_imm_b(instr)
            v1 = (regs[rs1] & 0xFFFFFFFF)
            v2 = (regs[rs2] & 0xFFFFFFFF)

            if v1 == v2:
                pc = pc + imm
            else:
                pc += 4
        elif funct3 == 6:
            #bltu
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            imm = get_imm_b(instr)
            v1 = regs[rs1] & 0xFFFFFFFF
            v2 = regs[rs2] & 0xFFFFFFFF

            if v1 < v2:
                pc = pc + imm
            else:
                pc += 4
    elif opcode == 0x23:
        funct3=get_funct3(instr)
        if funct3 == 0:
            rs1=get_rs1(instr)
            rs2=get_rs2(instr)
            imm = get_imm_s(instr)
            addr = regs[rs1]+imm
            write_byte(addr,regs[rs2] &0xff)
            pc+=4
        elif funct3 == 2:
            #sw
            rs1=get_rs1(instr)
            rs2=get_rs2(instr)
            imm = get_imm_s(instr)
            addr = regs[rs1]+imm
            write_4_bytes(addr,regs[rs2])
            #print(hex(addr),regs[rs2])
            pc+=4
        elif funct3==1:
            #sh
            rs1=get_rs1(instr)
            rs2=get_rs2(instr)
            imm = get_imm_s(instr)
            addr = regs[rs1]+imm
            val = regs[rs2] & 0xffff
            write_2_bytes(addr,val)
            pc+=4
    elif opcode == 0x03:
        funct3 = get_funct3(instr)
        if funct3 == 2:
            #lw
            imm = get_imm_i(instr)
            rs1 = get_rs1(instr)
            rd = get_rd(instr)
            addr = (regs[rs1]+imm)&0xffffffff
            val = get_4_bytes(addr)
            regs[rd] = val&0xffffffff
            pc+=4
        elif funct3==4:
            imm = get_imm_i(instr)
            rs1 = get_rs1(instr)
            rd = get_rd(instr)
            addr = (regs[rs1]+imm)&0xffffffff
            val = get_byte(addr)
            regs[rd] = val&0xff
            pc+=4
        elif funct3==0:
            imm = get_imm_i(instr)
            rs1 = get_rs1(instr)
            rd = get_rd(instr)
            addr = (regs[rs1] + imm) & 0xffffffff
            val = get_byte(addr)
            regs[rd] = sign_extend(val,8) & 0xffffffff
            pc+=4
        elif funct3==5:
            imm = get_imm_i(instr)
            rs1 = get_rs1(instr)
            rd = get_rd(instr)
            addr = (regs[rs1] + imm) & 0xffffffff
            b0 = get_byte(addr)
            b1 = get_byte(addr+1)
            val = b0 | (b1 << 8)
            regs[rd] = val & 0xffff
            pc+=4
        elif funct3==1:
            imm = get_imm_i(instr)
            rs1 = get_rs1(instr)
            rd = get_rd(instr)
            addr = (regs[rs1] + imm) & 0xffffffff
            b0 = get_byte(addr)
            b1 = get_byte(addr+1)
            val = b0 | (b1 << 8)
            regs[rd] = sign_extend(val ,16) & 0xffffffff
            pc+=4
    elif opcode == 0x33:
        funct3=get_funct3(instr)
        funct7=get_funct7(instr)
        if funct3 == 4 and funct7==1:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            if regs[rs2] == 0:
                regs[rd]=0xffffffff
            elif regs[rs1] == -2147483648 and regs[rs2] == -1:
                regs[rd] = 0x80000000
            else:
                regs[rd] = int(sign_extend(regs[rs1],32)/sign_extend(regs[rs2],32)) &0xffffffff
            pc+=4
        elif funct3==1 and funct7==0:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            regs[rd]=(regs[rs1] << (regs[rs2] & 0x1F)) &0xffffffff
            pc+=4
        elif funct3==5 and funct7==0:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            regs[rd]=(regs[rs1] >> (regs[rs2] & 0x1F)) &0xffffffff
            pc+=4
        elif funct3==0 and funct7==0:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            regs[rd] = (regs[rs1] + regs[rs2])&0xffffffff
            pc+=4
        elif funct3==0 and funct7==0x20:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            regs[rd] = (regs[rs1] - regs[rs2])&0xffffffff
            pc+=4
        elif funct3==7 and funct7==0:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            regs[rd] = (regs[rs1] & regs[rs2])&0xffffffff
            pc+=4
        elif funct3==6 and funct7==0:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            regs[rd] = (regs[rs1] | regs[rs2])&0xffffffff
            pc+=4
        elif funct3 == 0 and funct7==1:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            regs[rd] = sign_extend(regs[rs1],32)*sign_extend(regs[rs2],32)
            pc+=4
        elif funct3 == 3 and funct7==0:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            v1 =regs[rs1] & 0xffffffff
            v2 =regs[rs2] & 0xffffffff
            if v1 < v2:
                regs[rd] = 1
            else:
                regs[rd] = 0
            pc+=4
        elif funct3 == 1 and funct7 == 1:
            #MUL
            rs1=get_rs1(instr)
            rs2=get_rs2(instr)
            rd=get_rd(instr)

            v1 = sign_extend(regs[rs1] & 0xffffffff,32)
            v2 = sign_extend(regs[rs2] & 0xffffffff,32)
            result = v1 *v2
            regs[rd] = (result >> 32) & 0xffffffff
            pc+=4
        elif funct3 == 3 and funct7 == 1:
            #MULH
            rs1=get_rs1(instr)
            rs2=get_rs2(instr)
            rd=get_rd(instr)

            v1 = regs[rs1] & 0xffffffff
            v2 = regs[rs2] & 0xffffffff
            result = v1 *v2
            regs[rd] = (result >> 32) & 0xffffffff
            pc+=4
        elif funct3==4 and funct7==0:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            regs[rd] = (regs[rs1] ^ regs[rs2])&0xffffffff
            pc+=4

        elif funct3 == 5 and funct7==1:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            regs[rd] = regs[rs1]//regs[rs2]
            pc+=4
        elif funct3 == 6 and funct7==1:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            if regs[rs2] == 0:
                regs[rd]=regs[rs1]
            elif regs[rs1] == -2147483648 and regs[rs2] == -1:
                regs[rd] = 0
            else:
                regs[rd] = int(sign_extend(regs[rs1]&0xffffffff,32)%sign_extend(regs[rs2]&0xffffffff,32)) &0xffffffff
            pc+=4
        elif funct3 == 7 and funct7==1:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            if regs[rs2] == 0:
                regs[rd]=regs[rs1] & 0xffffffff
            else:
                regs[rd] = (int(regs[rs1]&0xffffffff)%(regs[rs2]&0xffffffff)) &0xffffffff
            pc+=4
        elif funct3==5 and funct7==0x20:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            regs[rd]=(sign_extend(regs[rs1]&0xffffffff,32) >> (regs[rs2] & 0x1F)) &0xffffffff
            pc+=4
        elif funct3 == 2 and funct7==0:
            rs1 = get_rs1(instr)
            rs2 = get_rs2(instr)
            rd = get_rd(instr)
            v1 =sign_extend(regs[rs1] & 0xffffffff,32)
            v2 =sign_extend(regs[rs2] & 0xffffffff,32)
            if v1 < v2:
                regs[rd] = 1
            else:
                regs[rd] = 0
            pc+=4
    elif opcode==0x2f:
        funct3=get_funct3(instr)
        funct5=get_funct5(instr)
        rs1 = get_rs1(instr)
        rs2 = get_rs2(instr)
        rd = get_rd(instr)
        addr = regs[rs1] & 0xffffffff
        val = get_4_bytes(addr)
        if funct3==0x02 and funct5==0x08:
            #AMOOR.w
            result = val | regs[rs2]
            write_4_bytes(addr,result&0xffffffff)
            regs[rd] = val& 0xffffffff
            pc+=4
        elif funct3==0x02 and funct5==0x0c:
            #AMOAND.w
            result = val & regs[rs2]
            write_4_bytes(addr,result&0xffffffff)
            regs[rd] = val& 0xffffffff
            pc+=4
        elif funct3==0x2 and funct5==0x0 :
            #AMOADD
            result = val + regs[rs2]
            write_4_bytes(addr,result&0xffffffff)
            regs[rd] = val& 0xffffffff
            pc+=4
        elif funct3==2 and funct5 == 0x2:
            #LR.W
            addr = regs[rs1] & 0xffffffff
            val = get_4_bytes(addr)
            reservation=addr
            regs[rd] = val & 0xffffffff
            pc+=4
        elif funct3 == 2 and funct5 == 0x3:
            if reservation == addr :
                write_4_bytes(addr,regs[rs2])
                regs[rd]=0
            else:
                regs[rd]=1
            reservation=None
            pc+=4
        elif funct3==0x2 and funct5==0x1 :
            #AMOSWAP
            old=get_4_bytes(addr)
            write_4_bytes(addr,regs[rs2]&0xffffffff)
            regs[rd] = old& 0xffffffff
            pc+=4
    else:
        print(f"Unhandled instruction! {hex(instr)} {hex(opcode)} {hex(pc)}")
load_image(ram_base,linux_image)
load_image(dtb_addr,dtb_image)
debug=False
tick=True
count=0
MTIP = (1 << 7)
try:
    while True:
        cpu_step(get_instr(pc))
        if count > 60500000:
            debug=False
        count+=1
        if tick==True:#clock
            clint_time+=1
            tick=False
        else:
            tick=True
        if get_mtimecmp()<=clint_time:
            csrs[0x344] |= MTIP#timer interrupt
        else:
            csrs[0x344] &= ~MTIP
        if (csrs[0x344] & MTIP) and (csrs[0x304] & MTIP) and (csrs[0x300] & 0x8) and csrs[0x305] != 0 and csrs[0x340] != 0:
            csrs[0x341] = pc
            csrs[0x342] = 0x80000007
            old_mie = (csrs[0x300] >> 3) & 1
            csrs[0x300] = (csrs[0x300] & ~(1 << 7)) | (old_mie << 7)
            csrs[0x300] &= ~0x8
            pc = csrs[0x305] & ~3
finally:
    pass
