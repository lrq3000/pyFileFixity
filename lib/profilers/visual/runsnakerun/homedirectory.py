"""Attempt to determine the current user's "system" directories"""
try:
##	raise ImportError
    from win32com.shell import shell, shellcon
except ImportError:
    shell = None
try:
    import _winreg
except ImportError:
    _winreg = None
import os, sys


## The registry keys where the SHGetFolderPath values appear to be stored
r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"

def _winreg_getShellFolder( name ):
    """Get a shell folder by string name from the registry"""
    k = _winreg.OpenKey(
        _winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
    )
    try:
        # should check that it's valid? How?
        return _winreg.QueryValueEx( k, name )[0]
    finally:
        _winreg.CloseKey( k )
def shell_getShellFolder( type ):
    """Get a shell folder by shell-constant from COM interface"""
    return shell.SHGetFolderPath(
        0,# null hwnd
        type, # the (roaming) appdata path
        0,# null access token (no impersonation)
        0 # want current value, shellcon.SHGFP_TYPE_CURRENT isn't available, this seems to work
    )
    
    

def appdatadirectory(  ):
    """Attempt to retrieve the current user's app-data directory

    This is the location where application-specific
    files should be stored.  On *nix systems, this will
    be the ${HOME}/.config directory.  On Win32 systems, it will be
    the "Application Data" directory.  Note that for
    Win32 systems it is normal to create a sub-directory
    for storing data in the Application Data directory.
    """
    if shell:
        # on Win32 and have Win32all extensions, best-case
        return shell_getShellFolder(shellcon.CSIDL_APPDATA)
    if _winreg:
        # on Win32, but no Win32 shell com available, this uses
        # a direct registry access, likely to fail on Win98/Me
        return _winreg_getShellFolder( 'AppData' )
    # okay, what if for some reason _winreg is missing? would we want to allow ctypes?
    ## default case, look for name in environ...
    for name in ['APPDATA', 'HOME']:
        if name in os.environ:
            return os.path.join( os.environ[name], '.config' )
    # well, someone's being naughty, see if we can get ~ to expand to a directory...
    possible = os.path.abspath(os.path.expanduser( '~/.config' ))
    if os.path.exists( possible ):
        return possible
    raise OSError( """Unable to determine user's application-data directory, no ${HOME} or ${APPDATA} in environment""" )

if __name__ == "__main__":
    print 'AppData', appdatadirectory()
    
