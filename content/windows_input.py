"""Original ctypes DirectInput 8 backend; nonexclusive reads, no motor effects.

Custom formats use enumerated object identities, not assumed device layouts.
Win32 types are fixed-width so ABI layout can also be checked on Linux hosts.
"""
import ctypes as C
import os
import uuid

DWORD=C.c_uint32
LONG=C.c_int32
WORD=C.c_uint16
PTR=C.c_void_p


class GUID(C.Structure):
    _fields_=[('a',DWORD),('b',WORD),('c',WORD),('d',C.c_ubyte*8)]

    @classmethod
    def parse(cls, text): return cls.from_buffer_copy(uuid.UUID(text).bytes_le)
    def text(self): return str(uuid.UUID(bytes_le=bytes(self)))


class DeviceInstance(C.Structure):
    _fields_=[('size',DWORD),('instance',GUID),('product',GUID),('type',DWORD),
              ('name',WORD*260),('product_name',WORD*260),('ff_driver',GUID),('usage_page',WORD),('usage',WORD)]


class ObjectInstance(C.Structure):
    _fields_=[('size',DWORD),('guid',GUID),('offset',DWORD),('type',DWORD),('flags',DWORD),
              ('name',WORD*260),('ff_max',DWORD),('ff_resolution',DWORD),('collection',WORD),
              ('designator',WORD),('usage_page',WORD),('usage',WORD),('dimension',DWORD),('exponent',WORD),('report',WORD)]


class ObjectFormat(C.Structure):
    _fields_=[('guid',C.POINTER(GUID)),('offset',DWORD),('type',DWORD),('flags',DWORD)]


class DataFormat(C.Structure):
    _fields_=[('size',DWORD),('object_size',DWORD),('flags',DWORD),('data_size',DWORD),
              ('count',DWORD),('objects',C.POINTER(ObjectFormat))]


class PropertyRange(C.Structure):
    _fields_=[('size',DWORD),('header_size',DWORD),('object',DWORD),('how',DWORD),('minimum',LONG),('maximum',LONG)]


def checked(result, operation):
    if result < 0: raise OSError(f'{operation}: DirectInput HRESULT 0x{result & 0xffffffff:08x}')


def method(pointer,index,*types):
    table=C.cast(pointer,C.POINTER(C.POINTER(PTR))).contents
    return C.WINFUNCTYPE(LONG,PTR,*types)(table[index])


def invoke(pointer,index,types=(),args=()):
    return method(pointer,index,*types)(pointer,*args)


def text_utf16(array):
    return bytes(array).decode('utf-16-le').split('\0',1)[0]


def format_objects(objects):
    """Return owned ctypes storage and decode table for all real axes/buttons."""
    entries=[]
    for obj in objects:
        kind=obj.type & 0xff;index=(obj.type>>8)&0xffff
        if index>255: continue
        if kind & 2: entries.append(('axis',index,obj))
        elif kind & 12: entries.append(('button',index,obj))
    entries.sort(key=lambda item:(item[0],item[1]))
    if not entries or len(entries)>512: raise ValueError('No supported joystick axes/buttons')
    seen=set();mapping=[];offset=0
    formats=(ObjectFormat*len(entries))()
    for i,(kind,index,obj) in enumerate(entries):
        if (kind,index) in seen: raise ValueError('Duplicate DirectInput object identity')
        seen.add((kind,index))
        formats[i]=ObjectFormat(C.pointer(obj.guid),offset,obj.type & 0x00ffffff,0)
        mapping.append((kind,index,offset))
        offset+=4 if kind=='axis' else 1
    size=(offset+3)&~3
    fmt=DataFormat(C.sizeof(DataFormat),C.sizeof(ObjectFormat),1,size,len(entries),formats)
    return fmt,formats,entries,mapping


def decode(data,mapping):
    axes={};buttons={}
    for kind,index,offset in mapping:
        if kind=='axis': axes[index]=int.from_bytes(data[offset:offset+4],'little',signed=True)
        else: buttons[index]=bool(data[offset]&0x80)
    return axes,buttons


class DirectInput:
    def __init__(self):
        if os.name!='nt': raise OSError('DirectInput requires Windows')
        self.pointer=PTR();self.dll=C.WinDLL('dinput8.dll')
        kernel=C.WinDLL('kernel32.dll');kernel.GetModuleHandleW.argtypes=[C.c_wchar_p];kernel.GetModuleHandleW.restype=PTR
        self.module=kernel.GetModuleHandleW(None)
        create=self.dll.DirectInput8Create
        create.argtypes=[PTR,DWORD,C.POINTER(GUID),C.POINTER(PTR),PTR];create.restype=LONG
        iid=GUID.parse('bf798031-483a-4da2-aa99-5d64ed369700')
        checked(create(self.module,0x0800,C.byref(iid),C.byref(self.pointer),None),'DirectInput8Create')

    def devices(self):
        result=[]
        callback_type=C.WINFUNCTYPE(LONG,C.POINTER(DeviceInstance),PTR)
        @callback_type
        def callback(info,context):
            d=info.contents
            result.append(('dinput:'+d.instance.text(),text_utf16(d.name)))
            return 1
        checked(invoke(self.pointer,4,(DWORD,callback_type,PTR,DWORD),(4,callback,None,1)),'EnumDevices')
        return result

    def close(self):
        if self.pointer:
            invoke(self.pointer,2);self.pointer=PTR()


def devices():
    api=DirectInput()
    try:return api.devices()
    finally:api.close()


class Joystick:
    def __init__(self,path):
        self.pointer=PTR();self.window=None;self.api=None
        self.axes={};self.buttons={}
        if not path.startswith('dinput:'): raise ValueError('Use a dinput:GUID from the list command on Windows')
        self.path=path
        try:
            self.api=DirectInput();found=dict(self.api.devices())
            if path not in found: raise OSError('Device not connected: '+path)
            self.name=found[path];guid=GUID.parse(path[7:])
            checked(invoke(self.api.pointer,3,(C.POINTER(GUID),C.POINTER(PTR),PTR),
                           (C.byref(guid),C.byref(self.pointer),None)),'CreateDevice')
            self.objects=[]
            callback_type=C.WINFUNCTYPE(LONG,C.POINTER(ObjectInstance),PTR)
            @callback_type
            def callback(info,context):
                self.objects.append(ObjectInstance.from_buffer_copy(bytes(info.contents)));return 1
            checked(invoke(self.pointer,4,(callback_type,PTR,DWORD),(callback,None,15)),'EnumObjects')
            self.format,self.formats,self.entries,self.mapping=format_objects(self.objects)
            checked(invoke(self.pointer,11,(C.POINTER(DataFormat),),(C.byref(self.format),)),'SetDataFormat')
            for kind,index,obj in self.entries:
                if kind=='axis':
                    prop=PropertyRange(C.sizeof(PropertyRange),16,obj.type & 0x00ffffff,2,-32768,32767)
                    checked(invoke(self.pointer,6,(PTR,C.POINTER(PropertyRange)),(PTR(4),C.byref(prop))),'Set axis range')
            self.user=C.WinDLL('user32.dll',use_last_error=True)
            self.user.CreateWindowExW.argtypes=[DWORD,C.c_wchar_p,C.c_wchar_p,DWORD,LONG,LONG,LONG,LONG,PTR,PTR,PTR,PTR]
            self.user.CreateWindowExW.restype=PTR
            self.user.DestroyWindow.argtypes=[PTR];self.user.DestroyWindow.restype=LONG
            # An invisible top-level built-in window belongs to this process,
            # unlike the console host's window; nonexclusive background access
            # keeps reading while Moon Sweepers owns focus.
            self.window=self.user.CreateWindowExW(0,'STATIC','MoonLab wheel input',0x80000000,0,0,1,1,None,None,self.api.module,None)
            if not self.window:raise OSError('Cannot create DirectInput ownership window')
            checked(invoke(self.pointer,13,(PTR,DWORD),(self.window,10)),'SetCooperativeLevel')
            checked(invoke(self.pointer,7),'Acquire')
            self.state=(C.c_ubyte*self.format.data_size)()
        except BaseException:
            self.close();raise

    def poll(self):
        # A lost/unplugged device exits the helper; explicit restart ensures
        # released pedals and a new calibration identity check before arming.
        checked(invoke(self.pointer,25),'Poll')
        checked(invoke(self.pointer,9,(DWORD,PTR),(len(self.state),C.cast(self.state,PTR))),'GetDeviceState')
        self.axes,self.buttons=decode(bytes(self.state),self.mapping)

    def close(self):
        if self.pointer:
            invoke(self.pointer,8);invoke(self.pointer,2);self.pointer=PTR()
        if self.window:
            self.user.DestroyWindow(self.window);self.window=None
        if self.api:self.api.close();self.api=None
