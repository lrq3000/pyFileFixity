Recursive/Relative Files Integrity Generator and Checker in Python (aka RFIGC)
=======================================================

Description
----------------
Recursively generate or check the integrity of files by MD5 and SHA1 hashes, size, modification date or by data structure integrity (only for images).

This script is originally meant to be used for data archival, by allowing an easy way to check for silent file corruption. Thus, this script uses relative paths so that you can easily compute and check the same redundant data copied on different mediums (hard drives, optical discs, etc.). This script is not meant for system files corruption notification, but is more meant to be used from times-to-times to check up on your data archives integrity.

This script was made for Python 2.7.6, but it should be easily adaptable to run on Python 3.x.

Example usage
----------------------
- To generate the database (only needed once):

```python rfigc.py -i "folderimages" -d "dbhash.csv" -g ```

- To check:

```python rfigc.py -i "folderimages" -d "dbhash.csv" -l log.txt -s ```

- To update your database by appending new files:

```python rfigc.py -i "folderimages" -d "dbhash.csv" -u -a ```

- To update your database by appending new files AND removing inexistent files:

```python rfigc.py -i "folderimages" -d "dbhash.csv" -u -a -r ```

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

Header Error Correction Code script
----------------------------------------------------

This script was made to be used in combination with other more common file redundancy generators (such as PAR2, I advise MultiPar). This is an additional layer of protection for your files: by using a higher resiliency rate on the headers of your files, you ensure that you will be probably able to open them in the future, avoiding the "critical spots" (where if you modify just one bit, your whole file may become unreadable, usually bits residing in the headers).

Todo
-------

- A variable error correction rate encoder:
each file would be encoded in ecc using a variable resiliency rate, using a high constant resiliency rate for the header part (resiliency rate stage 1, high), then a variable resiliency rate would be applied to the rest of the file's content, with a higher rate near the beginning of the file (resiliency rate stage 2, medium) which would lower progressively until the end of file (resiliency rate stage 3, the lowest). This can be seen as an extension of header-ecc.py. An unfinished attempt was done in structural-adaptive-ecc.py, feel free to have a look (the generation works correctly, there remains only to decode and error correct: the error correct would be similar to what is done in header-ecc.py, the part that is yet to be defined is how to read a stream of variable-sized ecc blocks in an ecc entry).
This variable error correction rate would allow to protect more the critical parts of a file (the header and the beginning of a file, for example in compressed file formats such as zip this is where the most importantly strings are encoded) for the same amount of storage as a standard constant error correction rate.
Furthermore, the currently designed format of the ecc file would allow two things that are not available in all current file ecc generators such as PAR2: 1- this would allow to partially repair a file, even if not all the blocks can be corrected (in PAR2, a file is repaired only if all blocks can be repaired, which is a shame because there are still other blocks that could be repaired and thus produce a less corrupted file) ; 2- the ecc file format is quite simple and readable, easy to process by any script, which would allow other softwares to also work on it (and it was also done in this way to be more resilient against error corruptions, so that even if an entry is corrupted, other entries are independent and can maybe be used, thus the ecc is very error tolerant).

- Integrate with https://github.com/Dans-labs/bit-recover ? (need to convert the perl script into python...).

- Speed optimize the Reed-Solomon library? (using Numpy or Cython? But I want to keep a pure python implementation available just in case, or make a Cython implementation that is also compatible with normal python). Use pprofile to check where to optimize first.
