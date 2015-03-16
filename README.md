pyFileFixity
=========

This project aims to provide a set of open source, cross-platform, easy to use and easy to maintain (readable code) to manage data for long term storage. The project is done in pure-Python to meet those criteria.

The problem of long term storage
-----------------------------------------------
Long term storage is a very difficult topic: it's like fighting with death (in this case, the death of data). Indeed, because of entropy, data will eventually fade away because of various silent errors such as bit rot. pyFileFixity aims to provide tools to detect any data corruption, but also fight data corruption by providing repairing tools (mainly via error correction codes, which is a way to produce redundant codes from your data so that you can later repair your data using these additional pieces of information).

The best tool ever invented to recover from data corruption are the error correction codes (forward error correction), which produce n blocks for a file cut in k blocks (with k < n), and then they can rebuild the whole file with any k blocks among the total n blocks available. This can be seen as a way to average the corruption error: on average, a bit will still have the same chance to be corrupted, but since you have more bits to represent the same data, you lower the overall chance to lose this bit.

The problem is that most theoretical and pratical works on error correcting codes has been done exclusively on channel transmission (such as 4G, internet, etc.), but not on data storage, which is very different for one reason: whereas in a channel we are in a spatial scheme (both the sender and the receiver are different entities in space but working at the same timescale), in data storage this is a temporal scheme: the sender was you storing the data on your medium at time t, and the receiver is again you but now retrieving the data at time t+x. Thus, the sender does not exist anymore, thus you cannot ask again some data if it's too much corrupted: in data storage, if a data is corrupted, it's lost for good, whereas in channel theory, a data can be submitted again if necessary.

Some attempts were made to translate channel theory and error correcting codes theory to data storage, the first being Reed-Solomon which spawned the RAID schema. Then CIRC (Cross-interleaved Reed–Solomon coding) was devised for use on optical discs to recover from scratches, which was necessary for the technology to be usable for consumers. Since then, new less-optimal but a lot faster algorithms such as LDPC, turbo-codes and fountain codes such as RaptorQ were invented (or rediscovered), but they are still marginally researched for data storage.

This project aims to first implement easy tools to evaluate strategies (filetamper.py) and file fixity (ie, detect if there are corruptions), and then the goal is to provide an open and easy framework to use different kinds of error correction codes to protect and repair files.

Applications included
-------------------------------

The project currently include the following pure-python applications:

- rfigc.py, a hash auditing tool, similar to md5deep/hashdeep, to compute a database of your files along with their metadata, so that later you can check if they were changed/corrupted.

- header_ecc.py, an error correction code using Reed-Solomon generator/corrector for files headers. The idea is to supplement other more common redundancy tools such as PAR2 (which is quite reliable), by adding more resiliency only on the critical parts of the files: their headers. Using this script, you can significantly higher the chance of recovering headers, which will allow you to at least open the files.

- filetamper.py is a quickly made file corrupter, it will erase or change characters in the specified file. This is useful for testing your various protecting strategies and file formats (eg: is PAR2 really resilient against corruption? Are zip archives still partially extractable after corruption or are rar archives better? etc.). Do not underestimate the usefulness of this tool, as you should always check the resiliency of your file formats and of your file protection strategies before relying on them.

- easy_profiler.py is just a quick and simple profiling tool to get you started quickly on what should be optimized to get more speed, if you want to contribute to the project feel free to propose a pull request! (Cython and other optimizations are welcome as long as they are cross-platform and that an alternative pure-python implementation is also available).

- structural_adaptive_ecc.py, a variable error correction rate encoder (kind of a generalization of header_ecc.py). See the TODO for more info. This isn't yet ready for production (generation is OK but no repair).

Recursive/Relative Files Integrity Generator and Checker in Python (aka RFIGC)
-------------------------------------------------------------------------------------------------------------------
Recursively generate or check the integrity of files by MD5 and SHA1 hashes, size, modification date or by data structure integrity (only for images).

This script is originally meant to be used for data archival, by allowing an easy way to check for silent file corruption. Thus, this script uses relative paths so that you can easily compute and check the same redundant data copied on different mediums (hard drives, optical discs, etc.). This script is not meant for system files corruption notification, but is more meant to be used from times-to-times to check up on your data archives integrity.

This script was made for Python 2.7.6, but it should be easily adaptable to run on Python 3.x.

### Example usage
- To generate the database (only needed once):

```python rfigc.py -i "folderimages" -d "dbhash.csv" -g ```

- To check:

```python rfigc.py -i "folderimages" -d "dbhash.csv" -l log.txt -s ```

- To update your database by appending new files:

```python rfigc.py -i "folderimages" -d "dbhash.csv" -u -a ```

- To update your database by appending new files AND removing inexistent files:

```python rfigc.py -i "folderimages" -d "dbhash.csv" -u -a -r ```

Note that by default, the script is by default in check mode, to avoid wrong manipulations. It will also alert you if you generate over an already existing database file.

### Arguments

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

The script is pure-python as its dependencies: it is thus completely cross-platform and open source. However, this imply that it is quite slow, but PyPy v2.5.0 was successfully tested against the script without any modification, and a speed increase of 5x could be observed. This is still slow but at least it's useable for real datasets.

Todo
-------

- A variable error correction rate encoder:
each file would be encoded in ecc using a variable resiliency rate, using a high constant resiliency rate for the header part (resiliency rate stage 1, high), then a variable resiliency rate would be applied to the rest of the file's content, with a higher rate near the beginning of the file (resiliency rate stage 2, medium) which would lower progressively until the end of file (resiliency rate stage 3, the lowest). This can be seen as an extension of header-ecc.py. An unfinished attempt was done in structural-adaptive-ecc.py, feel free to have a look (the generation works correctly, there remains only to decode and error correct: the error correct would be similar to what is done in header-ecc.py, the part that is yet to be defined is how to read a stream of variable-sized ecc blocks in an ecc entry).
This variable error correction rate would allow to protect more the critical parts of a file (the header and the beginning of a file, for example in compressed file formats such as zip this is where the most importantly strings are encoded) for the same amount of storage as a standard constant error correction rate.
Furthermore, the currently designed format of the ecc file would allow two things that are not available in all current file ecc generators such as PAR2: 1- this would allow to partially repair a file, even if not all the blocks can be corrected (in PAR2, a file is repaired only if all blocks can be repaired, which is a shame because there are still other blocks that could be repaired and thus produce a less corrupted file) ; 2- the ecc file format is quite simple and readable, easy to process by any script, which would allow other softwares to also work on it (and it was also done in this way to be more resilient against error corruptions, so that even if an entry is corrupted, other entries are independent and can maybe be used, thus the ecc is very error tolerant).

- Integrate with https://github.com/Dans-labs/bit-recover ? (need to convert the perl script into python...).

- Speed optimize the Reed-Solomon library? (using Numpy or Cython? But I want to keep a pure python implementation available just in case, or make a Cython implementation that is also compatible with normal python). Use pprofile to check where to optimize first.
