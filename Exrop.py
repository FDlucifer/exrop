from Solver import ChainBuilder
from RopChain import RopChain
from os import popen

def parseRopGadget(filename):
    cmd = 'ROPgadget --nojop --binary {} --only "pop|xchg|add|sub|xor|mov|ret" | grep "ret$"'.format(filename)
    with popen(cmd) as fp:
        sample_gadgets = dict()
        datas = fp.read().strip().split("\n")
        datas.sort(key=len) # sort by length
        for data in datas:
            addr,insns = data.split(" : ")
            addr = int(addr, 16)
            sample_gadgets[addr] = insns
        return sample_gadgets

class Exrop(object):
    def __init__(self, binary):
        self.binary = binary
        self.chain_builder = ChainBuilder()

    def find_gadgets(self, cache=False):
        if cache:
            fcname = "./{}.exrop_cache".format(self.binary.replace("/", "_"))
            try:
                with open(fcname, "rb") as fc:
                    objpic = fc.read()
                    self.chain_builder.load_analyzed_gadgets(objpic)
                    return
            except FileNotFoundError:
                fc = open(fcname, "wb")
        gadgets = parseRopGadget(self.binary)
        self.chain_builder.load_list_gadget_string(gadgets)
        self.chain_builder.analyzeAll()
        if cache:
            objpic = self.chain_builder.save_analyzed_gadgets()
            fc.write(objpic)
            fc.close()

    def load_raw_gadgets(self, gadgets):
        pass

    def set_regs(self, regs, next_call=None):
        self.chain_builder.set_regs(regs)
        self.chain_builder.solve_chain()
        ropchain = self.chain_builder.build_chain(next_call)
        return ropchain

    def set_writes(self, writes, next_call=None):
        self.chain_builder.set_writes(writes)
        self.chain_builder.solve_chain_write()
        ropchain = self.chain_builder.build_chain(next_call)
        return ropchain

    def set_string(self, strs, next_call=None):
        BSIZE = 8
        writes = dict()
        for addr,sstr in strs.items():
            tmpaddr = 0
            for i in range(0, len(sstr), BSIZE):
                tmpstr = int.from_bytes(bytes(sstr[i:i+BSIZE]+"\x00", 'utf-8'), 'little')
                writes[addr+tmpaddr] = tmpstr
                tmpaddr += BSIZE
        return self.set_writes(writes, next_call)

    def func_call(self, func_addr, args, rwaddr=None, type="sysv"):
        order_reg = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
        regs = dict()
        ropchain = RopChain()
        for i in range(len(args)):
            arg = args[i]
            if isinstance(arg, str):
                assert rwaddr, "Please define read write addr"
                arg += "\x00"
                chain = self.set_string({rwaddr:arg})
                ropchain.merge_ropchain(chain)
                regs[order_reg[i]] = rwaddr
                rwaddr += len(arg)
                continue
            regs[order_reg[i]] = arg
        chain = self.set_regs(regs, func_addr)
        ropchain.merge_ropchain(chain)
        return ropchain
