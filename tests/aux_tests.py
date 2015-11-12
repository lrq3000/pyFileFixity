import filecmp

def check_eq_files(path1, path2):
    """ Return True if both files are identical, False otherwise """
    return filecmp.cmp(path1, path2, shallow=False)

def check_eq_folders(path1, path2):
    """ Return True if both folders have totally identical files, False otherwise """
    d = filecmp.dircmp(path1, path2)
    a = d.left_only + d.right_only + d.diff_files + d.funny_files
    if a:
        return False
    else:
        return True
