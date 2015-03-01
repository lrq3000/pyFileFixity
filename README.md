Recursive/Relative Files Integrity Generator and Checker in Python (aka RFIGC)
=======================================================

Description
----------------
Recursively generate or check the integrity of files by MD5 and SHA1 hashes, size, modification date or by data structure integrity (only for images).

This script is originally meant to be used for data archival, by allowing an easy way to check for silent file corruption. Thus, this script uses relative paths so that you can easily compute and check the same redundant data copied on different mediums (hard drives, optical discs, etc.). This script is not meant for system files corruption notification, but is more meant to be used from times-to-times to check up on your data archives integrity.

Example usage
----------------------
- To generate the database (only needed once):
```python python rfigc.py -i "folderimages" -d "dbhash.csv" -g ```

- To check:
```python python rfigc.py -i "folderimages" -d "dbhash.csv" -l log.txt -s ```

- To update your database by appending new files:
```python python rfigc.py -i "folderimages" -d "dbhash.csv" -u -a ```

- To update your database by appending new files AND removing inexistent files:
```python python rfigc.py -i "folderimages" -d "dbhash.csv" -u -a -r ```

Note that by default, the script is by default in check mode, to avoid wrong manipulations. It will also alert you if you generate over an already existing database file.

Arguments
----------------

```
  -h, --help            show a help message and exit
  -i /path/to/root/folder, --input /path/to/root/folder
                        Path to the root folder from where the scanning will occ
ur.
  -d /some/folder/databasefile.csv, --database /some/folder/databasefile.csv
                        Path to the csv file containing the hash informations.
  -l /some/folder/filename.log, --log /some/folder/filename.log
                        Path to the log file. (Output will be piped to both the
stdout and the log file)
  -s, --structure_check
                        Check images structures for corruption?
  -e /some/folder/errorsfile.csv, --errors_file /some/folder/errorsfile.csv
                        Path to the error file, where errors at checking will be
 stored in CSV for further processing by other softwares (such as file repair so
ftwares).
  -m, --disable_modification_date_checking
                        Disable modification date checking.
  --skip_missing        Skip missing files when checking (useful if you split yo
ur files into several mediums, for example on optical discs with limited capacit
y).
  -g, --generate        Generate the database? (omit this parameter to check ins
tead of generating).
  -f, --force           Force overwriting the database file even if it already e
xists (if --generate).
  -u, --update          Update database (you must also specify --append or --rem
ove).
  -a, --append          Append new files (if --update).
  -r, --remove          Remove missing files (if --update).
```
