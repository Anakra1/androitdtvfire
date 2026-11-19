"""Check the actual ELF tables used by old Android loaders, not just file headers."""
import struct

def symbols(raw):
    assert raw[:4]==b'\x7fELF' and raw[5]==1
    bits=raw[4];wide=bits==2
    phoff=struct.unpack_from('<Q' if wide else '<I',raw,32 if wide else 28)[0]
    size,count=struct.unpack_from('<HH',raw,54 if wide else 42)
    loads=[];dynamic=None
    for i in range(count):
        p=struct.unpack_from('<IIQQQQQQ' if wide else '<IIIIIIII',raw,phoff+i*size)
        kind=p[0];off,va,length,align=(p[2],p[3],p[5],p[7]) if wide else (p[1],p[2],p[4],p[7])
        if kind==1:loads.append((va,off,length,align))
        if kind==2:dynamic=(off,length)
    assert dynamic
    def offset(va):
        for start,off,length,_ in loads:
            if start<=va<start+length:return off+va-start
        raise AssertionError('ELF address outside a loadable segment')
    tags={};step=16 if wide else 8
    for pos in range(dynamic[0],dynamic[0]+dynamic[1],step):
        key,value=struct.unpack_from('<QQ' if wide else '<II',raw,pos)
        if key==0:break
        tags[key]=value
    assert tags.get(4),'DT_HASH missing: incompatible with the reported loader'
    assert tags.get(0x6ffffef5),'GNU hash absent: retain support on newer loaders'
    assert not set(tags)&{0x6000000f,0x60000010,0x60000011,0x60000012,35,36,37,0x6fffe000},'New packed relocation format'
    table=offset(tags[4]);buckets,chains=struct.unpack_from('<II',raw,table)
    assert buckets>0 and chains>1 and table+8+4*(buckets+chains)<=len(raw)
    names=offset(tags[5]);symbol_table=offset(tags[6]);syment=tags[11]
    def elf_hash(text):
        value=0
        for byte in text.encode():
            value=(value<<4)+byte;high=value&0xf0000000
            if high:value^=high>>24
            value&=~high
        return value
    found=[]
    for name in ('CBRStart','CBRStop'):
        index=struct.unpack_from('<I',raw,table+8+4*(elf_hash(name)%buckets))[0];seen=set()
        while index:
            assert index<chains and index not in seen;seen.add(index)
            sym=struct.unpack_from('<IBBHQQ' if wide else '<IIIBBH',raw,symbol_table+index*syment)
            start=names+sym[0];text=raw[start:raw.index(b'\x00',start)].decode()
            if text==name:
                assert (sym[3] if wide else sym[5])!=0
                assert (sym[4] if wide else sym[1])>0
                found.append(name);break
            index=struct.unpack_from('<I',raw,table+8+4*(buckets+index))[0]
        else:raise AssertionError(name+' missing from legacy hash lookup')
    return dict(elf_class=bits,machine=int.from_bytes(raw[18:20],'little'),legacy_hash=True,gnu_hash=True,exports=found,page_alignment=min(p[3] for p in loads))
