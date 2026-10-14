"""macOS generic-password access via Security.framework, never secret argv."""
import ctypes as C
import sys
from .store import ResearchError
SERVICE='org.vibe-research.credentials'

class Keychain:
    def __init__(self,service=SERVICE):
        if sys.platform!='darwin':raise ResearchError('系统钥匙串仅支持 macOS；其他系统请使用环境变量或显式文件配置')
        self.service=service
        self.cf=C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        self.sec=C.CDLL('/System/Library/Frameworks/Security.framework/Security')
        self.cf.CFStringCreateWithCString.argtypes=[C.c_void_p,C.c_char_p,C.c_uint32];self.cf.CFStringCreateWithCString.restype=C.c_void_p
        self.cf.CFDataCreate.argtypes=[C.c_void_p,C.c_void_p,C.c_long];self.cf.CFDataCreate.restype=C.c_void_p
        self.cf.CFDictionaryCreate.argtypes=[C.c_void_p,C.POINTER(C.c_void_p),C.POINTER(C.c_void_p),C.c_long,C.c_void_p,C.c_void_p];self.cf.CFDictionaryCreate.restype=C.c_void_p
        self.cf.CFRelease.argtypes=[C.c_void_p]
        self.cf.CFDataGetLength.argtypes=[C.c_void_p];self.cf.CFDataGetLength.restype=C.c_long
        self.cf.CFDataGetBytePtr.argtypes=[C.c_void_p];self.cf.CFDataGetBytePtr.restype=C.c_void_p
        for name,args in [('SecItemAdd',[C.c_void_p,C.POINTER(C.c_void_p)]),('SecItemCopyMatching',[C.c_void_p,C.POINTER(C.c_void_p)]),('SecItemUpdate',[C.c_void_p,C.c_void_p]),('SecItemDelete',[C.c_void_p])]:
            fn=getattr(self.sec,name);fn.argtypes=args;fn.restype=C.c_int32
    def constant(self,name):return C.c_void_p.in_dll(self.sec,name).value
    def query(self,account,operation,value=None):
        owned=[]
        def string(value):
            ptr=self.cf.CFStringCreateWithCString(None,value.encode(),0x08000100);owned.append(ptr);return ptr
        def dictionary(values):
            n=len(values);ptr=self.cf.CFDictionaryCreate(None,(C.c_void_p*n)(*values.keys()),(C.c_void_p*n)(*values.values()),n,None,None);owned.append(ptr);return ptr
        result=C.c_void_p()
        try:
            base={self.constant('kSecClass'):self.constant('kSecClassGenericPassword'),self.constant('kSecAttrService'):string(self.service),self.constant('kSecAttrAccount'):string(account)}
            if operation=='read':
                base[self.constant('kSecReturnData')]=C.c_void_p.in_dll(self.cf,'kCFBooleanTrue').value
                base[self.constant('kSecMatchLimit')]=self.constant('kSecMatchLimitOne')
                code=self.sec.SecItemCopyMatching(dictionary(base),C.byref(result))
                if code==-25300:return None
                if code:raise ResearchError('钥匙串访问未完成（系统状态 '+str(code)+'）；请在本机配置引导中处理')
                return C.string_at(self.cf.CFDataGetBytePtr(result),self.cf.CFDataGetLength(result)).decode()
            if operation=='delete':
                code=self.sec.SecItemDelete(dictionary(base))
                if code not in (0,-25300):raise ResearchError('无法删除此工具的钥匙串项')
                return
            raw=value.encode();data=self.cf.CFDataCreate(None,raw,len(raw));owned.append(data)
            attrs={self.constant('kSecValueData'):data}
            code=self.sec.SecItemAdd(dictionary({**base,**attrs}),None)
            if code==-25299:code=self.sec.SecItemUpdate(dictionary(base),dictionary(attrs))
            if code:raise ResearchError('钥匙串保存未完成（系统状态 '+str(code)+'）；未降级为明文保存')
        finally:
            if result.value:self.cf.CFRelease(result)
            for ptr in reversed(owned):self.cf.CFRelease(ptr)
    def read(self,account):return self.query(account,'read')
    def save(self,account,value):return self.query(account,'save',value)
    def delete(self,account):return self.query(account,'delete')
