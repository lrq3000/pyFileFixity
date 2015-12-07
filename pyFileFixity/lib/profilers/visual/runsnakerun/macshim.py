def macshim():
    """Shim to run 32-bit on 64-bit mac as a sub-process"""
    import subprocess, sys
    subprocess.call([
        sys.argv[0] + '32'
    ]+sys.argv[1:], 
        env={"VERSIONER_PYTHON_PREFER_32_BIT":"yes"}
    )
