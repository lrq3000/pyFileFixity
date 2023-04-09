pyFileFixity
============

|PyPI-Status| |PyPI-Versions| |PyPI-Downloads|

|Build-Status| |Coverage|

pyFileFixity provides a suite of open source, cross-platform, easy
to use and easy to maintain (readable code) to protect and manage data
for long term storage/archival, and also test the performance of any data protection algorithm.

The project is done in pure-Python to meet those criteria,
although cythonized extensions are available for core routines to speed up encoding/decoding,
but always with a pure python specification available so as to allow long term replication.

Here is an example of what pyFileFixity can do:

|Example|

On the left, this is the original image.

At the center, the same image but
with a few symbols corrupted (only 3 in header and 2 in the rest of the file,
which equals to 5 bytes corrupted in total, over 19KB which is the total file size).
Only a few corrupted bytes are enough to make the image looks like totally
unrecoverable, and yet we are lucky, because the image could be unreadable at all
if any of the "magic bytes" were to be corrupted!

At the right, the corrupted image was repaired using `header_ecc.py` of pyFileFixity.
This repaired only the image header (ie, the first part of the file), so only the first
3 corrupted bytes were repaired, not the 2 bytes in the rest of the file, but we can see
the image looks like it's totally repaired! And the best thing is that it only costed the generation
of a "ecc repair file", which size is only 3.3KB (17% of the original file)!

This works because most files will store the most important information to read them at
their beginning, also called "file's header", so repairing this part will almost always ensure
the possibility to read the file (even if the rest of the file is still corrupted, if the header is safe,
you can read it).

Of course, you can also protect the whole file, not only the header, using pyFileFixity's
`structural_adaptive_ecc.py`. You can also detect any corruption using `rfigc.py`.

------------------------------------------

.. contents:: Table of contents
   :backlinks: top

Quickstart
----------

Runs on Python 3 up to Python 3.11. Both PyPy 3 and PyPy 2 are supported. Older versions such as Python 2.7.10 are still being automatically unit tested with continuous integration but support can be dropped at any moment.

- To install or update on Python 3:

``pip install --upgrade pyfilefixity``

- For Python 2.7, the latest working version was v3.0.2:

``pip install --upgrade pyfilefixity==3.0.2``

- Once installed, the suite of tools can be accessed from a centralized interface script called ``pff`` which provides several subcommands, to list them:

``pff --help``

You should see:

::

    usage: pff [-h]
               {hash,rfigc,header,header_ecc,hecc,whole,structural_adaptive_ecc,saecc,protect,repair,recover,repair_ecc,recc,dup,replication_repair,restest,resilience_tester,filetamper,speedtest,ecc_speedtest}
               ...

    positional arguments:
      {hash,rfigc,header,header_ecc,hecc,whole,structural_adaptive_ecc,saecc,protect,repair,recover,repair_ecc,recc,dup,replication_repair,restest,resilience_tester,filetamper,speedtest,ecc_speedtest}
        hash (rfigc)        Check files integrity fast by hash, size, modification date or by data structure integrity.
        header (header_ecc, hecc)
                            Protect/repair files headers with error correction codes
        whole (structural_adaptive_ecc, saecc, protect, repair)
                            Protect/repair whole files with error correction codes
        recover (repair_ecc, recc)
                            Utility to try to recover damaged ecc files using a failsafe mechanism, a sort of recovery
                            mode (note: this does NOT recover your files, only the ecc files, which may then be used to
                            recover your files!)
        dup (replication_repair)
                            Repair files from multiple copies of various storage mediums using a majority vote
        restest (resilience_tester)
                            Run tests to quantify robustness of a file protection scheme (can be used on any, not just
                            pyFileFixity)
        filetamper          Tamper files using various schemes
        speedtest (ecc_speedtest)
                            Run error correction encoding and decoding speedtests

    options:
      -h, --help            show this help message and exit

- Every subcommands provide their own more detailed help instructions, eg for the ``hash`` submodule:

``pff hash --help``

- To generate a monitoring database (to later check very fast which files are corrupted, but cannot repair anything but filesystem metadata):

``pff hash -i "your_folder" -d "dbhash.csv" -g -f -l "log.txt"``

Note: this also works for a single file, just replace "your_folder" by "your_file.ext".

- Later, to check which files were corrupted:

``pff hash -i "your_folder" -d "dbhash.csv" -l log.txt -s -e errors.csv``

- To use this monitoring database to recover filesystem metadata such as files names and directory layout by filescraping from files contents:

``pff hash -i "your_folder" -d "dbhash.csv" -l "log.txt" -o "output_folder" --filescraping_recovery``

- To protect files headers with a file called ``hecc.txt``:

``pff header -i "your_folder" -d "hecc.txt" -l "log.txt" -g -f --ecc_algo 3``

- To repair files headers and store the repaired files in ``output_folder``:

``pff header -i "your_folder" -d "hecc.txt" -o "output_folder" -l "log.txt" -c -v --ecc_algo 3``

- To protect whole files with a file called ``ecc.txt``:

``pff whole -i "your_folder" -d "ecc.txt" -l "log.txt" -g -f -v --ecc_algo 3``

- To repair whole files:

``pff whole -i "your_folder" -d "ecc.txt" -o "output_folder" -l "log.txt" -c -v --ecc_algo 3``

Note that ``header`` and ``whole`` can also detect corrupted files and even which blocks inside a file, but they are much slower than ``hash``.

- To try to recover a damaged ecc file ``ecc.txt`` using an index file ``ecc.txt.idx`` (index file is generated automatically with ecc.txt):

``pff recovery -i "ecc.txt" --index "ecc.txt.idx" -o "ecc_repaired.txt" -l "log.txt" -v -f``

- To try to recover a damaged ecc file ``ecc.txt`` without an index file (you can tweak the ``-t`` parameter from 0.0 to 1.0, 1.0 producing many false positives):

``pff recovery -i "ecc.txt" -o "ecc_repaired.txt" -l "log.txt" -v -f -t 0.4``

- To repair your files using multiple duplicated copies that you have stored on different mediums:

``pff dup -i "path/to/dir1" "path/to/dir2" "path/to/dir3" -o "path/to/output" --report "rlog.csv" -f -v``

- If you have previously generated a rfigc database, you can use it to enhance the replication repair:

``pff dup -i "path/to/dir1" "path/to/dir2" "path/to/dir3" -o "path/to/output" -d "dbhash.csv" --report "rlog.csv" -f -v``

- To run tests on your recovery tools, you can make a Makefile-like configuration file and use the Resiliency Tester submodule:

``pff restest -i "your_folder" -o "test_folder" -c "resiliency_tester_config.txt" -m 3 -l "testlog.txt" -f``

- Internally, ``pff restest`` uses ``pff filetamper`` to tamper files with various schemes, but you can also use ``pff filetamper`` directly.

- To run speedtests of encoding/decoding error correction codes on your machine:

``pff speedtest``

- In case the ``pff`` command does not work, it can be replaced with ``python -m pyFileFixity.pff`` .

- DEPRECATED (because Gooey is not maintained anymore it seems): To use the GUI with any tool, use ``--gui`` and do not supply any other argument, eg: ``python rfigc.py --gui``.

- You can also use `PyPy <http://pypy.org/>`_ or Cython to hugely speedup the processing time of any tool here.

The problem of long term storage
--------------------------------

Why are data corrupted with time? One sole reason: entropy.
Entropy refers to the universal tendency for systems to become
less ordered over time. Data corruption is exactly that: a disorder
in bits order. In other words: *the Universe hates your data*.

Long term storage is thus a very difficult topic: it's like fighting with
death (in this case, the death of data). Indeed, because of entropy,
data will eventually fade away because of various silent errors such as
bit rot or cosmic rays. pyFileFixity aims to provide tools to detect any data
corruption, but also fight data corruption by providing repairing tools.

The only solution is to use a principle of engineering that is long
known and which makes bridges and planes safe: add some **redundancy**.

There are only 2 ways to add redundancy:

-  the simple way is to **duplicate** the object (also called replication),
   but for data storage, this eats up a lot of storage and is not optimal.
   However, if storage is cheap, then this is a good solution, as it is
   much faster than encoding with error correction codes. For replication to work,
   at least 3 duplicates are necessary at all times, so that if one fails, it must
   replaced asap. As sailors say: "Either bring 1 compass or 3 compasses, but never
   two, because then you won't know which one is correct if one fails."
   Indeed, with 3 duplicates, if you frequently monitor their integrity
   (eg, with hashes), then if one fails, simply do a majority vote:
   the bit value given by 2 of the duplicates is probably correct.
-  the second way, the optimal tools ever invented to recover
   from data corruption, are the **error correction codes** (forward
   error correction), which are a way to smartly produce redundant codes
   from your data so that you can later repair your data using these
   additional pieces of information (ie, an ECC generates n blocks for a
   file cut in k blocks (with k < n), and then the ecc code can rebuild
   the whole file with (at least) any k blocks among the total n blocks
   available). In other words, you can correct up to (n-k) erasures. But
   error correcting codes can also detect and repair automatically where
   the errors are (fully automatic data repair for you !), but at the
   cost that you can then only correct (n-k)/2 errors.

Error correction can seem a bit magical, but for a reasonable intuition,
it can be seen as a way to average the corruption error rate: on
average, a bit will still have the same chance to be corrupted, but
since you have more bits to represent the same data, you lower the
overall chance to lose this bit.

The problem is that most theoretical and pratical works on error
correcting codes has been done almost exclusively on channel
transmission (such as 4G, internet, etc.), but not on data storage,
which is very different for one reason: whereas in a channel we are in a
spatial scheme (both the sender and the receiver are different entities
in space but working at the same timescale), in data storage this is a
temporal scheme: the sender was you storing the data on your medium at
time t, and the receiver is again you but now retrieving the data at
time t+x. Thus, the sender does not exist anymore, thus you cannot ask
the sender to send again some data if it's too much corrupted: in data
storage, if a data is corrupted, it's lost for good, whereas in channel theory,
parts of the data can be submitted again if necessary.

Some attempts were made to translate channel theory and error correcting
codes theory to data storage, the first being Reed-Solomon which spawned
the RAID schema. Then CIRC (Cross-interleaved Reed-Solomon coding) was
devised for use on optical discs to recover from scratches, which was
necessary for the technology to be usable for consumers. Since then, new
less-optimal but a lot faster algorithms such as LDPC, turbo-codes and
fountain codes such as RaptorQ were invented (or rediscovered), but they
are still marginally researched for data storage.

This project aims to, first, implement easy tools to evaluate strategies
(filetamper.py) and file fixity (ie, detect if there are corruptions),
and then the goal is to provide an open and easy framework to use
different kinds of error correction codes to protect and repair files.

Also, the ecc file specification is made to be simple and resilient to
corruption, so that you can process it by your own means if you want to,
without having to study for hours how the code works (contrary to PAR2
format).

In practice, both approaches are not exclusive, and the best is to
combine them: protect the most precious data with error correction codes,
then duplicate them as well as less sensitive data across multiple storage mediums.
Hence, this suite of data protection tools, just like any other such suite, is not
sufficient to guarantee your data is protected, you must have an active data curation
strategy which includes regularly checking your data and replacing copies that are damaged.

For a primer on storage mediums and data protection strategies, see `this post I wrote <https://web.archive.org/web/20220529125543/https://superuser.com/questions/374609/what-medium-should-be-used-for-long-term-high-volume-data-storage-archival/873260>`_.

Why not just use RAID ?
-----------------------

RAID is clearly insufficient for long-term data storage, and in fact it
was primarily meant as a cheap way to get more storage (RAID0) or more
availability (RAID1) of data, not for archiving data, even on a medium
timescale:

-  RAID 0 is just using multiple disks just like a single one, to extend
   the available storage. Let's skip this one.
-  RAID 1 is mirroring one disk with a bit-by-bit copy of another disk.
   That's completely useless for long term storage: if either disk
   fails, or if both disks are partially corrupted, you can't know what
   are the correct data and which aren't. As an old saying goes: "Never
   take 2 compasses: either take 3 or 1, because if both compasses show
   different directions, you will never know which one is correct, nor
   if both are wrong." That's the principle of Triplication.
-  RAID 5 is based on the triplication idea: you have n disks (but least
   3), and if one fails you can recover n-1 disks (resilient to only 1
   disk failure, not more).
-  RAID 6 is an extension of RAID 5 which is closer to error-correction
   since you can correct n-k disks. However, most (all?) currently
   commercially available RAID6 devices only implements recovery for at
   most n-2 (2 disks failures).
-  In any case, RAID cannot detect silent errors automatically, thus you
   either have to regularly scan, or you risk to lose some of your data
   permanently, and it's far more common than you can expect (eg, with
   RAID5, it is enough to have 2 silent errors on two disks on the same
   bit for the bit to be unrecoverable). That's why a limit of only 1 or
   2 disks failures is just not enough.

On the opposite, ECC can correct n-k disks (or files). You can configure
n and k however you want, so that for example you can set k = n/2, which
means that you can recover all your files from only half of them! (once
they are encoded with an ecc file of course).

There also are new generation RAID solutions, mainly software based,
such as SnapRAID or ZFS, which allow you to configure a virtual RAID
with the value n-k that you want. This is just like an ecc file (but a
bit less flexible, since it's not a file but a disk mapping, so that you
can't just copy it around or upload it to a cloud backup hosting). In
addition to recover (n-k) disks, they can also be configured to recover
from partial, sectors failures inside the disk and not just the whole
disk (for a more detailed explanation, see Plank, James S., Mario Blaum,
and James L. Hafner. "SD codes: erasure codes designed for how storage
systems really fail." FAST. 2013.).

The other reason RAID is not adapted to long-term storage, is that it
supposes you store your data on hard-drives exclusively. Hard drives
aren't a good storage medium for the long term, for two reasons:

| 1- they need a regular plug to keep the internal magnetic disks
  electrified (else the data will just fade away when there's no
  residual electricity).
| 2- the reading instrument is directly included and merged with the
  data (this is the green electronic board you see from the outside, and
  the internal head). This is good for quick consumer use (don't need to
  buy another instrument: the HDD can just be plugged and it works), but
  it's very bad for long term storage, because the reading instrument is
  bound to fail, and a lot faster than the data can fade away: this
  means that even if your magnetic disks inside your HDD still holds
  your data, if the controller board or the head doesn't work anymore,
  your data is just lost. And a head (and a controller board) are almost
  impossible to replace, even by professionals, because the pieces are
  VERY hard to find (different for each HDD production line) and each
  HDD has some small physical defects, thus it's impossible to reproduce
  that too (because the head is so close to the magnetic disk that if
  you try to do that manually you'll probably fail).

In the end, it's a lot better to just separate the storage medium of
data, with the reading instrument. The medium I advise is optical disks
(whether it's BluRay, DVD, CD or whatever), because the reading
instrument is separate, and the technology (laser reflecting on bumps
and/or pits) is kind of universal, so that even if the technology is
lost one day (deprecated by newer technologies, so that you can't find
the reading instrument anymore because it's not sold anymore), you can
probably emulate a laser using some software to read your optical disk,
just like what the CAMiLEON project did to recover data from the
LaserDiscs of the BBC Domesday Project (see Wikipedia).

Applications included
---------------------

The project currently include the following pure-python applications:

-  rfigc.py (subcommand: ``hash``), a hash auditing tool, similar to md5deep/hashdeep, to
   compute a database of your files along with their metadata, so that
   later you can check if they were changed/corrupted.

-  header\_ecc.py (subcommand: ``header``), an error correction code using Reed-Solomon
   generator/corrector for files headers. The idea is to supplement
   other more common redundancy tools such as PAR2 (which is quite
   reliable), by adding more resiliency only on the critical parts of
   the files: their headers. Using this script, you can significantly
   higher the chance of recovering headers, which will allow you to at
   least open the files.

-  structural\_adaptive\_ecc.py (subcommand: ``whole``), a variable error correction rate
   encoder (kind of a generalization of header\_ecc.py). This script
   allows to generate an ecc file for the whole content of your files,
   not just the header part, using a variable resilience rate: the
   header part will be the most protected, then the rest of each file
   will be progressively encoded with a smaller and smaller resilience
   rate. The assumption is that important information is stored first,
   and then data becomes less and less informative (and thus important,
   because the end of the file describes less important details). This
   assumption is very true for all compressed kinds of formats, such as
   JPG, ZIP, Word, ODT, etc...

-  repair\_ecc.py (subcommand: ``recovery``), a script to repair the structure (ie, the entry and
   fields markers/separators) of an ecc file generated by header\_ecc.py
   or structural\_adaptive\_ecc.py. The goal is to enhance the
   resilience of ecc files against corruption by ensuring that their
   structures can be repaired (up to a certain point which is very high
   if you use an index backup file, which is a companion file that is
   generated along an ecc file).

-  filetamper.py (subcommand: ``filetamper``) is a quickly made file corrupter, it will erase or
   change characters in the specified file. This is useful for testing
   your various protecting strategies and file formats (eg: is PAR2
   really resilient against corruption? Are zip archives still partially
   extractable after corruption or are rar archives better? etc.). Do
   not underestimate the usefulness of this tool, as you should always
   check the resiliency of your file formats and of your file protection
   strategies before relying on them.

-  replication\_repair.py (subcommand: ``dup``) takes advantage of your multiple copies
   (replications) of your data over several storage mediums to recover
   your data in case it gets corrupted. The goal is to take advantage of
   the storage of your archived files into multiple locations: you will
   necessarily make replications, so why not use them for repair?
   Indeed, it's good practice to keep several identical copies of your data
   on several storage mediums, but in case a corruption happens,
   usually you will just drop the corrupted copies and keep the intacts ones.
   However, if all copies are partially corrupted, you're stuck. This script
   aims to take advantage of these multiple copies to recover your data,
   without generating a prior ecc file. It works simply by reading through all
   your different copies of your data, and it casts a majority vote over each
   byte: the one that is the most often occuring will be kept. In engineering,
   this is a very common strategy used for very reliable systems such as
   space rockets, and is called "triple-modular redundancy", because you need
   at least 3 copies of your data for the majority vote to work (but the more the
   better).

-  resiliency\_tester.py (subcommand: ``restest``) allows you to test the robustness of the
   corruption correction of the scripts provided here (or any other
   command-line app). You just have to copy the files you want to test inside a
   folder, and then the script will copy the files into a test tree, then it
   will automatically corrupt the files randomly (you can change the parameters
   like block burst and others), then it will run the file repair command-lines
   you supply and finally some stats about the repairing power will be
   generated. This allows you to easily and objectively compare different set
   of parameters, or even different file repair solutions, on the very data
   that matters to you, so that you can pick the best option for you.

-  ecc\_speedtest.py (subcommand: ``speedtest``) is a simple error correction codes
   encoder/decoder speedtest. It allows to easily change parameters for the test.
   This allows to assess how fast your machine can encode/decode with the selected
   parameters, which can be especially useful to plan ahead for how many files you
   can reasonably plan to protect with error correction codes (which are time consuming).

-  DEPRECATED: easy\_profiler.py is just a quick and simple profiling tool to get
   you started quickly on what should be optimized to get more speed, if
   you want to contribute to the project feel free to propose a pull
   request! (Cython and other optimizations are welcome as long as they
   are cross-platform and that an alternative pure-python implementation
   is also available).

Note that all tools are primarily made for command-line usage (type
script.py --help to get extended info about the accepted arguments), but
you can also use rfigc.py and header\_ecc.py with a GUI by using the
--gui argument (must be the first and only one argument supplied). The
GUI is provided as-is and minimal work will be done to maintain it (the
focus will stay on functionality rather than ergonomy).

IMPORTANT: it is CRITICAL that you use the same parameters for
correcting mode as when you generated the database/ecc files (this is
true for all scripts in this bundle). Of course, some options must be
changed: -g must become -c to correct, and --update is a particular
case. This works this way on purpose for mainly two reasons: first
because it is very hard to autodetect the parameters from a database
file alone and it would produce lots of false positives, and secondly
(the primary reason) is that storing parameters inside the database file
is highly unresilient against corruption (if this part of the database
is tampered, the whole becomes unreadable, while if they are stored
outside or in your own memory, the database file is always accessible).
Thus, it is advised to write down the parameters you used to generate
your database directly on the storage media you will store your database
file on (eg: if it's an optical disk, write the parameters on the cover
or directly on the disk using a marker), or better memorize them by
heart. If you forget them, don't panic, the parameters are always stored
as comments in the header of the generated ecc files, but you should try
to store them outside of the ecc files anyway.

For users: what's the advantage of pyFileFixity?
------------------------------------------------

Pros:

-  Open application and open specifications under the MIT license (you
   can do whatever you want with it and tailor it to your needs if you
   want to, or add better decoding procedures in the future as science
   progress so that you can better recover your data from your already
   generated ecc file).
-  Highly reliable file fixity watcher: rfigc.py will tell you without
   any ambiguity using several attributes if your files have been
   corrupted or not, and can even check for images if the header is
   valid (ie: if the file can still be opened).
-  Readable ecc file format (compared to PAR2 and most other similar
   specifications).
-  Highly resilient ecc file format against corruption (not only are
   your data protected by ecc, the ecc file is protected too against
   critical spots, both because there is no header so that each track is
   independent and if one track is corrupted beyond repair then other
   ecc tracks can still be read, and a .idx file will be generated to
   repair the structure of the ecc file to recover all tracks).
-  Very safe and conservative approach: the recovery process checks that
   the recovery was successful before committing a repaired block.
-  Partial recovery allowed (even if a file cannot be completely
   recovered, the parts that can will be repaired and then the rest that
   can't be repaired will be recopied from the corrupted version).
-  Support directory processing: you can encode an ecc file for a whole
   directory of files (with any number of sub-directories and depth).
-  No limit on the number of files, and it can recursively protect files
   in a directory tree.
-  Variable resiliency rate and header-only resilience, ensuring that
   you can always open your files even if partially corrupted (the
   structure of your files will be saved, so that you can use other
   softwares to repair beyond if this set of script is not sufficient to
   totally repair).
-  Support for erasures (null bytes) and even errors-and-erasures, which
   literally doubles the repair capabilities. To my knowledge, this is
   the only freely available parity software that supports erasures.
-  Display the predicted total ecc file size given your parameters,
   and the total time it will take to encode/decode.
-  Your original files are still accessible as they are, protection files
   such as ecc files live alongside your original data. Contrary to
   other data protection schemes such as PAR2 which encode the whole
   data in par archive files that replace your original files and
   are not readable without decoding.
-  Opensourced under the very permissive MIT licence, do whatever you
   want!

Cons:

-  Cannot protect meta-data, such as folders paths. The paths are
   stored, but cannot be recovered (yet? feel free to contribute if you
   know how). Only files are protected. Thus if your OS or your storage
   medium crashes and truncate a whole directory tree, the directory
   tree can't be repaired using the ecc file, and thus you can't access
   the files neither. However, you can use file scraping to extract the
   files even if the directory tree is lost, and then use RFIGC.py to
   reorganize your files correctly. There are alternatives, see the
   chapters below: you can either package all your files in a single
   archive using DAR or ZIP (thus the ecc will also protect meta-data), or see
   DVDisaster as an alternative solution, which is an ecc generator with
   support for directory trees meta-data (but only on optical disks).
-  Can only repair errors and erasures (characters that are replaced by
   another character), not deletion nor insertion of characters. However
   this should not happen with any storage medium (truncation can occur
   if the file bounds is misdetected, in this case pyFileFixity can
   partially repair the known parts of the file, but cannot recover the
   rest past the truncation, except if you used a resiliency rate of at
   least 0.5, in which case any message block can be recreated with only
   using the ecc file).
-  Cannot recreate a missing file from other available files (except you
   have set a resilience\_rate at least 0.5), contrary to Parchives
   (PAR1/PAR2). Thus, you can only repair a file if you still have it
   (and its ecc file!) on your filesystem. If it's missing, pyFileFixity
   cannot do anything (yet, this will be implemented in the future).

Note that the tools were meant for data archival (protect files that you
won't modify anymore), not for system's files watching nor to protect
all the files on your computer. To do this, you can use a filesystem
that directly integrate error correction code capacity, such as ZFS.

Recursive/Relative Files Integrity Generator and Checker in Python (aka RFIGC)
------------------------------------------------------------------------------

Recursively generate or check the integrity of files by MD5 and SHA1
hashes, size, modification date or by data structure integrity (only for
images).

This script is originally meant to be used for data archival, by
allowing an easy way to check for silent file corruption. Thus, this
script uses relative paths so that you can easily compute and check the
same redundant data copied on different mediums (hard drives, optical
discs, etc.). This script is not meant for system files corruption
notification, but is more meant to be used from times-to-times to check
up on your data archives integrity (if you need this kind of application,
see `avpreserve's fixity <https://github.com/avpreserve/fixity>`_).

Example usage
~~~~~~~~~~~~~

-  To generate the database (only needed once):

``pff hash -i "your_folder" -d "dbhash.csv" -g``

-  To check:

``pff hash -i "your_folder" -d "dbhash.csv" -l log.txt -s``

-  To update your database by appending new files:

``pff hash -i "your_folder" -d "dbhash.csv" -u -a``

-  To update your database by appending new files AND removing
   inexistent files:

``pff hash -i "your_folder" -d "dbhash.csv" -u -a -r``

Note that by default, the script is by default in check mode, to avoid
wrong manipulations. It will also alert you if you generate over an
already existing database file.

Arguments
~~~~~~~~~

::

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
      
      --filescraping_recovery          Given a folder of unorganized files, compare to the database and restore the filename and directory structure into the output folder.
      -o, --output          Path to the output folder where to output the files reorganized after --recover_from_filescraping.

Header Error Correction Code script
-----------------------------------

This script was made to be used in combination with other more common
file redundancy generators (such as PAR2, I advise MultiPar). This is an
additional layer of protection for your files: by using a higher
resiliency rate on the headers of your files, you ensure that you will
be probably able to open them in the future, avoiding the "critical
spots", also called "fracture-critical" in redundancy engineering (where
if you modify just one bit, your whole file may become unreadable,
usually bits residing in the headers - in other words, a single blow
makes the whole thing collapse, just like non-redundant bridges).

An interesting benefit of this approach is that it has a low storage
(and computational) overhead that scales linearly to the number of
files, whatever their size is: for example, if we have a set of 40k
files for a total size of 60 GB, with a resiliency\_rate of 30% and
header\_size of 1KB (we limit to the first 1K bytes/characters = our
file header), then, without counting the hash per block and other
meta-data, the final ECC file will be about 2 \* resiliency\_rate \*
number\_of\_files \* header\_size = 24.5 MB. This size can be lower if
there are many files smaller than 1KB. This is a pretty low storage
overhead to backup the headers of such a big number of files.

The script is pure-python as are its dependencies: it is thus completely
cross-platform and open source. However, this imply that it is quite
slow, but PyPy v2.5.0 was successfully tested against the script without
any modification, and a speed increase of more 100x could be observed,
so that you can expect a rate of more than 1MB/s, which is quite fast.

Structural Adaptive Error Correction Encoder
--------------------------------------------

This script implements a variable error correction rate encoder: each
file is ecc encoded using a variable resiliency rate -- using a high
constant resiliency rate for the header part (resiliency rate stage 1,
high), then a variable resiliency rate is applied to the rest of the
file's content, with a higher rate near the beginning of the file
(resiliency rate stage 2, medium) which progressively decreases until
the end of file (resiliency rate stage 3, the lowest).

The idea is that the critical parts of files usually are placed at the
top, and data becomes less and less critical along the file. What is
meant by critical is both the critical spots (eg: if you tamper only one
character of a file's header you have good chances of losing your entire
file, ie, you cannot even open it) and critically encoded information
(eg: archive formats usually encode compressed symbols as they go along
the file, which means that the first occurrence is encoded, and then the
archive simply writes a reference to the symbol. Thus, the first
occurrence is encoded at the top, and subsequent encoding of this same
data pattern will just be one symbol, and thus it matters less as long
as the original symbol is correctly encoded and its information
preserved, we can always try to restore the reference symbols later).
Moreover, really redundant data will be placed at the top because they
can be reused a lot, while data that cannot be too much compressed will
be placed later, and thus, corruption of this less compressed data is a
lot less critical because only a few characters will be changed in the
uncompressed file (since the data is less compressed, a character change
on the not-so-much compressed data won't have very significant impact on
the uncompressed data).

This variable error correction rate should allow to protect more the
critical parts of a file (the header and the beginning of a file, for
example in compressed file formats such as zip or jpg this is where the
most importantly strings are encoded) for the same amount of storage as
a standard constant error correction rate.

Of course, you can set the resiliency rate for each stage to the values
you want, so that you can even do the opposite: setting a higher
resiliency rate for stage 3 than stage 2 will produce an ecc that is
greater towards the end of the contents of your files.

Furthermore, the currently designed format of the ecc file would allow
two things that are not available in all current file ecc generators
such as PAR2:

1. it allows to partially repair a file, even if not all
the blocks can be corrected (in PAR2, a file is repaired only if all
blocks can be repaired, which is a shame because there are still other
blocks that could be repaired and thus produce a less corrupted file) ;

2. the ecc file format is quite simple and readable, easy to process by
any script, which would allow other softwares to also work on it (and it
was also done in this way to be more resilient against error
corruptions, so that even if an entry is corrupted, other entries are
independent and can maybe be used, thus the ecc is very error tolerant.
This idea was implemented in repair\_ecc.py but it could be extended,
especially if you know the pattern of the corruption).

The script structural-adaptive-ecc.py implements this idea, which can be
seen as an extension of header-ecc.py (and in fact the idea was the
other way around: structural-adaptive-ecc.py was conceived first but was
too complicated, then header-ecc.py was implemented as a working
lessened implementation only for headers, and then
structural-adaptive-ecc.py was finished using header-ecc.py code
progress). It works, it was a quite well tested for my own needs on
datasets of hundred of GB, but it's not foolproof so make sure you test
the script by yourself to see if it's robust enough for your needs (any
feedback about this would be greatly appreciated!).

ECC Algorithms
--------------

You can specify different ecc algorithms using the ``--ecc_algo`` switch.

For the moment, only Reed-Solomon is implemented, but it's universal
so you can modify its parameters in lib/eccman.py.

Two Reed-Solomon codecs are available, they are functionally equivalent
and thoroughly unit tested.

-  ``--ecc_algo 1``: use the first Reed-Solomon codec in galois field 2^8 of root 3 with fcr=1.
   This is the slowest implementation (but also the most easy code to understand).
-  ``--ecc_algo 2``: same as algo 1 but with a faster functions.
-  ``--ecc_algo 3``: use the second codec, which is the fastest.
   The generated ECC will be compatible with algo 1 and 2.
-  ``--ecc_algo 4``: also use the second, fastest RS codec, but
   with different parameters (US FAA ADSB UAT RS FEC norm),
   thus the generated ECC won't be compatible with algo 1 to 3.
   But do not be scared, the ECC will work just the same.

Cython implementation
---------------------

This section describes how to use the Cython implementation. However,
you should first try PyPy, as it may give great performances too.

Simply follow the instruction to install the `reedsolo <https://github.com/tomerfiliba-org/reedsolomon>`_ module with
the cythonized module.

Then make sure to use ``ecc_algo=3`` in all your ``eccman`` calls, and you
are then good to go, the cythonized module ``creedsolo`` will always be used
for both encoding and decoding transparently.

THE REST OF THIS SECTION IS OLD AND DEPRECATED, because the Cython compilation is now
done directly in the Reed-Solomon submodules, instead of here, so you
should not need to worry about it, just pip install with the requirements.txt
and you should be set. The information below is left for historical purposes:

A speedy Cython implementation of the Reed-Solomon library is included.
It should provide C-speed for all scripts (as long as you use
--ecc\_algo 1 or 2, not 3 nor 4). It is not needed, since a pure-python
implementation is used by default, but it can be useful if you want to
encode big datasets of several hundred of GB.

If you want to build the C/Cython implementation, do the following:

1- Install a C compiler for your platform. On Linux, gcc should already
be installed. On Windows, you need to use the Visual Studio C compiler
(not MinGW nor Cygwin gcc, they won't work). You can use the "Microsoft
Visual C++ Compiler for Python 2.7", and follow these instructions to
make it work if you have Python < 2.7.10:

https://github.com/cython/cython/wiki/CythonExtensionsOnWindows

2- cd to this folder (where pyFileFixity resides), and execute the
following command:

``python setup.py build_ext --inplace --compiler=msvc``

If everything goes alright, the C compiler will compile the .c files
(that were pre-generated by Cython) and you can then use PyFileFixity
scripts just as usual and you should see a huge speedup. Else, if it
doesn't work, you might need to generate .c files using Cython for your
platform (because the pre-generated .c files may be incompatible with
your platform). To do that, you just need to install Cython, which is an
easy task with nowadays Python distributions such as Anaconda: download
32-bit Anaconda installer (on Windows you should avoid the 64-bit, it
may produce weird issues with Cython), then after install, open the
Anaconda Command Prompt and execute: ``conda install cython``. This will
install all the necessary stuff along the cython library. Then you can
simply execute again the command
``python setup.py build_ext --inplace --compiler=msvc`` and it will this
time rebuild from scratch, by autodetecting that you have Cython
installed, the setup.py script will automatically generate .c files from
.pyx files and then .pyd files (binaries) from .c files.

If you get issues, you can see the following post on how to install
Cython:

https://github.com/cython/cython/wiki/InstallingOnWindows

3- You can now launch pyFileFixity like usual, it should automatically
detect the C/Cython compiled files and use that to speedup processing.

Note about speed: Also, use a smaller --max\_block\_size to greatly
speedup the operations! That's the trick used to compute very quickly RS
ECC on optical discs. You give up a bit of resiliency of course (because
blocks are smaller, thus you protect a smaller number of characters per
ECC. In the end, this should not change much about real resiliency, but
in case you get a big bit error burst on a contiguous block, you may
lose a whole block at once. That's why using RS255 is better, but it's
very time consuming. However, the resiliency ratios still hold, so for
any other case of bit-flipping with average-sized bursts, this should
not be a problem as long as the size of the bursts is smaller than an
ecc block.)

In case of a catastrophic event
-------------------------------

TODO: write more here

In case of a catastrophic event of your data due to the failure of your
storage media (eg: your hard drive crashed), then follow the following
steps:

1- use dd\_rescue to make a full bit-per-bit verbatim copy of your drive
before it dies. The nice thing with dd\_rescue is that the copy is
exact, and also that it can retries or skip in case of bad sectors (it
won't crash on your suddenly at half the process).

2- Use testdisk to restore partition or to copy files based on partition
filesystem informations.

3- If you could not recover your files, you can try file scraping using
`photorec <http://www.cgsecurity.org/wiki/PhotoRec>`_ or
`plaso  <http://plaso.kiddaland.net/>`_ other similar tools as
a last resort to extract data based only from files content (no filename,
often uncorrect filetype, file boundaries may be wrong so some data
may be cut off, etc.).

4- If you used pyFileFixity before the failure of your storage media,
you can then use your pre-computed databases to check that files are
intact (rfigc.py) and if they aren't, you can recover them (using
header\_ecc.py and structural\_adaptive\_ecc.py). It can also help if
you recovered your files via data scraping, because your files will be
totally unorganized, but you can use a previously generated database
file to recover the full names and directory tree structure using
rfigc.py --filescraping\_recover.

Also, you can try to fix some of your files using specialized repairing
tools (but remember that such tool cannot guarantee you the same
recovering capacity as an error correction code - and in addition, error
correction code can tell you when it has recovered successfully). For
example:

-  for tar files, you can use `fixtar <https://github.com/BestSolution-at/fixtar>`_.
   Similar tools (but older): `tarfix <http://www.dmst.aueb.gr/dds/sw/unix/tarfix/>`_
   and `tar-repair <https://www.datanumen.com/tar-repair/>`_.
-  for RAID mounting and recovery, you can use "Raid faster - recover
   better" (rfrb) tool by Sabine Seufert and Christian Zoubek:
   https://github.com/lrq3000/rfrb
-  if your unicode strings were mangled (ie, you see weird symbols),
   try this script that will automatically demangle them:
   https://github.com/LuminosoInsight/python-ftfy
-  to repair tabular (2D) data such as .csv, try
   `Carpenter <https://pypi.python.org/pypi/Carpenter/>`_.
-  tool to identify corrupted files in ddrescue images: 
   `ddrescue-ffile <https://github.com/Salamek/ddrescue-ffile>`_

Protecting directory tree meta-data
-----------------------------------

One main current limitation of pyFileFixity is that it cannot protect
the directory tree meta-data. This means that in the worst case, if a
silent error happens on the inode pointing to the root directory that
you protected with an ecc, the whole directory will vanish, and all the
files inside too. In less worst cases, sub-directories can vanish, but
it's still pretty bad, and since the ecc file doesn't store any
information about inodes, you can't recover the full path.

The inability to store these meta-data is because of two choices in the
design: 1- portability: we want the ecc file to work even if we move the
root directory to another place or another storage medium (and of
course, the inode would change), 2- cross-platform compatibility:
there's no way to get and store directory meta-data for all platforms,
but of course we could implement specific instructions for each main
platform, so this point is not really a problem.

To workaround this issue (directory meta-data are critical spots), other
softwares use a one-time storage medium (ie, writing your data along
with generating and writing the ecc). This way, they can access at
the bit level the inode info, and they are guaranted that the inodes
won't ever change. This is the approach taken by DVDisaster: by using
optical mediums, it can compute inodes that will be permanent, and thus
also encode that info in the ecc file. Another approach is to create a
virtual filesystem specifically to store just your files, so that you
manage the inode yourself, and you can then copy the whole filesystem
around (which is really just a file, just like a zip file - which can
also be considered as a mini virtual file system in fact) like
`rsbep <http://users.softlab.ntua.gr/~ttsiod/rsbep.html>`_.

Here the portability principle of pyFileFixity prevents this approach.
But you can mimic this workaround on your hard drive for pyFileFixity to
work: you just need to package all your files into one file. This way,
you sort of create a virtual file system: inside the archive, files and
directories have meta-data just like in a filesystem, but from the
outside it's just one file, composed of bytes that we can just encode to
generate an ecc file - in other words, we removed the inodes portability
problem, since this meta-data is stored relatively inside the archive,
the archive manage it, and we can just encode this info like any other
stream of data! The usual way to make an archive from several files is
to use TAR, but this will generate a solid archive which will prevent
partial recovery. An alternative is to use DAR, which is a non-solid
archive version of TAR, with lots of other features too. If you also
want to compress, you can just use ZIP (with DEFLATE algorithm) your
files (this also generates a non-solid archive). You can then use
pyFileFixity to generate an ecc file on your DAR or ZIP archive, which
will then protect both your files just like before and the directories
meta-data too now.

Tools like pyFileFixity (or which can be used as complements)
-------------------------------------------------------------

Here are some tools with a similar philosophy to pyFileFixity, which you
can use if they better fit your needs, either as a replacement of
pyFileFixity or as a complement (pyFileFixity can always be used to
generate an ecc file):

-  `DAR (Disk ARchive) <http://dar.linux.free.fr/>`__: similar to tar
   but non-solid thus allows for partial recovery and per-file access,
   plus it saves the directory tree meta-data -- see catalog isolation
   -- plus it can handle error correction natively using PAR2 and
   encryption. Also supports incremental backup, thus it's a very nice
   versatile tool. Crossplatform and opensource.
-  `DVDisaster <http://dvdisaster.net/>`__: error correction at the bit
   level for optical mediums (CD, DVD and BD / BluRay Discs). Very good,
   it also protects directory tree meta-data and is resilient to
   corruption (v2 still has some critical spots but v3 won't have any).
-  rsbep tool that is part of dvbackup package in Debian: allows to
   generate an ecc of a stream of bytes. Great to pipe to dar and/or gz
   for your backups, if you're on unix or using cygwin.
-  `rsbep modification by Thanassis
   Tsiodras <http://users.softlab.ntua.gr/~ttsiod/rsbep.html>`__:
   enhanced rsbep to avoid critical spots and faster speed. Also
   includes a "freeze" script to encode your files into a virtual
   filesystem (using Python/FUSE) so that even meta-data such as
   directory tree are fully protected by the ecc. Great script, but not
   maintained, it needs some intensive testing by someone knowledgeable
   to guarantee this script is reliable enough for production.
-  Parchive (PAR1, PAR2, MultiPar): well known error correction file
   generator. The big advantage of Parchives is that an ecc block
   depends on multiple files: this allows to completely reconstruct a
   missing file from scratch using files that are still available. Works
   good for most people, but most available Parchive generators are not
   satisfiable for me because 1- they do not allow to generate an ecc
   for a directory tree recursively (except MultiPar, and even if it is
   allowed in the PAR2 specs), 2- they can be very slow to generate
   (even with multiprocessor extensions, because the galois field is
   over 2^16 instead of 2^8, which is very costly), 3- the spec is not
   very resilient to errors and tampering over the ecc file, as it
   assumes the ecc file won't be corrupted (I also tested, it's still a
   bit resilient, but it could be a lot more with some tweaking of the
   spec), 4- it doesn't allow for partial recovery (recovering blocks
   that we can and pass the others that are unrecoverable): with PAR2, a
   file can be restored fully or it cannot be at all.
-  Zip (with DEFLATE algorithm, using 7-Zip or other tools): allows to
   create non-solid archives which are readable by most computers
   (ubiquitous algorithm). Non-solid archive means that a zip file can
   still unzip correct files even if it is corrupted, because files are
   encoded in blocks, and thus even if some blocks are corrupted, the
   decoding can happen. A `fast implementation with enhanced compression
   is available in pure Go <https://github.com/klauspost/compress>`__
   (good for long storage).
-  TestDisk: for file scraping, when nothing else worked.
-  dd\_rescue: for disk scraping (allows to forcefully read a whole disk
   at the bit level and copy everything it can, passing bad sector with
   options to retry them later on after a first full pass over the
   correct sectors).
-  ZFS: a file system which includes ecc correction directly. The whole
   filesystem, including directory tree meta-data, are protected. If you
   want ecc protection on your computer for all your files, this is the
   way to go.
-  Encryption: technically, you can encrypt your files without losing
   too much redundancy, as long as you use an encryption scheme that is
   block-based such as DES: if one block gets corrupted, it won't be
   decryptable, but the rest of the files' encrypted blocks should be
   decryptable without any problem. So encrypting with such algorithms
   leads to similar files as non-solid archives such as deflate zip. Of
   course, for very long term storage, it's better to avoid encryption
   and compression (because you raise the information contained in a
   single block of data, thus if you lose one block, you lose more
   data), but if it's really necessary to you, you can still maintain
   high chances of recovering your files by using block-based
   encryption/compression (note: block-based encryption can
   be seen as the equivalent of non-solid archives for compression,
   because the data is compressed/encrypted in independent blocks,
   thus allowing partial uncompression/decryption).
-  `SnapRAID <http://snapraid.sourceforge.net/>`__
-  `par2ools <https://github.com/jmoiron/par2ools>`__: a set of
   additional tools to manage par2 archives
-  `Checkm <https://pypi.python.org/pypi/Checkm/0.4>`__: a tool similar
   to rfigc.py
-  `BagIt <https://en.wikipedia.org/wiki/BagIt>`__ with two python
   implementations `here <https://pypi.python.org/pypi/pybagit/>`__ and
   `here <https://pypi.python.org/pypi/bagit/>`__: this is a file
   packaging format for sharing and storing archives for long term
   preservation, it just formalizes a few common procedures and meta
   data that are usually added to files for long term archival (such as
   MD5 digest).
-  `RSArmor <https://github.com/jap/rsarm>`__ a tool based on
   Reed-Solomon to encode binary data files into hexadecimal, so that
   you can print the characters on paper. May be interesting for small
   datasets (below 100 MB).
-  `Ent <https://github.com/lsauer/entropy>`__ a tool to analyze the
   entropy of your files. Can be very interesting to optimize the error
   correction algorithm, or your compression tools.
-  `HashFS <https://pypi.python.org/pypi/hashfs/>`_ is a non-redundant,
   duplication free filesystem, in Python. **Data deduplication** is very
   important for large scale long term storage: since you want your data
   to be redundant, this means you will use an additional storage space
   for your redundant copies that will be proportional to your original data.
   Having duplicated data will consume more storage and more processing
   time, for no benefit. That's why it's a good idea to deduplicate your data
   prior to create redundant copies: this will be faster and save you money.
   Deduplication can either be done manually (by using duplicates removers)
   or systematically and automatically using specific filesystems such as
   zfs (with deduplication enabled) or hashfs.
-  Paper as a storage medium: paper is not a great storage medium,
   because it has low storage density (ie, you can only store at most 
   about 100 KB) and it can also degrade just like other storage mediums,
   but you cannot check that automatically since it's not digital. However,
   if you are interested, here are a few softwares that do that:
   `Paper key <http://en.wikipedia.org/wiki/Paper_key>`_,
   `Paperbak <http://www.ollydbg.de/Paperbak/index.html>`_,
   `Optar <http://ronja.twibright.com/optar/>`_,
   `dpaper <https://github.com/penma/dpaper>`_,
   `QR Backup <http://blog.liw.fi/posts/qr-backup/>`_,
   `QR Backup (another) <http://blog.shuningbian.net/2009/10/qrbackup.php>`_,
   `QR Backup (again another) <http://git.pictorii.com/index.php?p=qrbackup.git&a=summary>`_,
   `QR Backup (again) <http://hansmi.ch/software/qrbackup>`_,
   `and finally a related paper <http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.303.3101&rep=rep1&type=pdf>`_.
-  AVPreserve tools, most notably `fixity <https://github.com/avpreserve/fixity>`_ 
   to monitor for file changes (similarly to rfigc, but actively as a daemon)
   and `interstitial <https://github.com/avpreserve/interstitial>`_ to detect
   interstitial errors in audio digitization workflows (great to ensure you
   correctly digitized a whole audio file into WAV without any error).

FAQ
---

-  Can I compress my data files and my ecc file?

As a rule of thumb, you should ALWAYS keep your ecc file in clear
text, so under no compression nor encryption. This is because in case
the ecc file gets corrupted, if compressed/encrypted, the
decompression/decrypting of the corrupted parts may completely flaw
the whole structure of the ecc file.

Your data files, that you want to protect, *should* remain in clear
text, but you may choose to compress them if it drastically reduces
the size of your files, and if you raise the resilience rate of your
ecc file (so compression may be a good option if you have an
opportunity to trade the file size reduction for more ecc file
resilience). Also, make sure to choose a non-solid compression
algorithm like DEFLATE (zip) so that you can still decode correct
parts even if some are corrupted (else with a solid archive, if one
byte is corrupted, the whole archive may become unreadable).

However, in the case that you compress your files, you should generate
the ecc file only *after* compression, so that the ecc file applies to
the compressed archive instead of the uncompressed files, else you
risk being unable to correct your files because the uncompression of
corrupted parts may output gibberish, and length extended corrupted
parts (and if the size is different, Reed-Solomon will just freak
out).

-  Can I encrypt my data files and my ecc file ?

NEVER encrypt your ecc file, this is totally useless and
counterproductive.

You can encrypt your data files, but choose a non-solid algorithm
(like AES if I'm not mistaken) so that corrupted parts do not prevent
the decoding of subsequent correct parts. Of course, you're lowering a
bit your chances of recovering your data files by encrypting them (the
best chance to keep data for the long term is to keep them in clear
text), but if it's really necessary, using a non-solid encrypting
scheme is a good compromise.

You can generate an ecc file on your encrypted data files, thus
*after* encryption, and keep the ecc file in clear text (never encrypt
nor compress it). This is not a security risk at all since the ecc
file does not give any information on the content inside your
encrypted files, but rather just redundant info to correct corrupted
bytes (however if you generate the ecc file on the data files before
encryption, then it's clearly a security risk, and someone could
recover your data without your permission).

- What medium should I use to store my data?

The details are long and a bit complicated (I may write a complete article
about it in the future), but the tl;dr answer is that you should use *optical disks*,
because it decouples the storage medium and the reading hardware
(eg, at the opposite we have hard drives, which contains both the reading
hardware and the storage medium, so if one fails, you lose both)
and because it's most likely future-proof (you only need a laser, which
is universal, the laser's parameters can always be tweaked).

From scientific studies, it seems that, at the time of writing this (2015),
BluRay HTL disks are the most resilient against environmental degradation.
To raise the duration, you can also put optical disks in completely opaque boxes
(to avoid light degradation) and in addition you can put any storage medium
(not only optical disks, but also hard drives and anything really) in
*completely* air-tight and water-tight bags or box and put in a fridge or a freezer.
This is a law of nature: lower the temperature, lower will be the entropy, in other
words lower will be the degradation over time. It works the same with digital data.

- What file formats are the most recoverable?

It's difficult to advise a specific format. What we can do is advise the characteristics
of a good file format:

  * future-proof (should be readable in the future).
  * non-solid (ie, divised into indepedent blocks, so that a corruption to one block doesn't cause a problem to the decoding of other blocks).
  * open source implementation available.
  * minimize corruption impact (ie, how much of the file becomes unreadable with a partial corruption? Only the partially corrupted area, or other valid parts too?).
  * No magic bytes or header importance (ie, corrupting the header won't prevent opening the file).

There are a few studies about the most resilient file formats, such as:

  * `"Just one bit in a million: On the effects of data corruption in files" by Volker Heydegger <http://lekythos.library.ucy.ac.cy/bitstream/handle/10797/13919/ECDL038.pdf?sequence=1>`_.
  * `"Analysing the impact of file formats on data integrity" by Volker Heydegger <http://old.hki.uni-koeln.de/people/herrmann/forschung/heydegger_archiving2008_40.pdf>`_.
  * `"A guide to formats", by The UK national archives <http://www.nationalarchives.gov.uk/documents/information-management/guide-to-formats.pdf>`_ (you want to look at the Recoverability entry in each table).

- What is Reed-Solomon?

If you have any question about Reed-Solomon codes, the best place to ask is probably here (with the incredible Dilip Sarwate): http://www.dsprelated.com/groups/comp.dsp/1.php?searchfor=reed%20solomon

Also, you may want to read the following resources:

  * "`Reed-Solomon codes for coders <https://en.wikiversity.org/wiki/Reed%E2%80%93Solomon_codes_for_coders>`_", free practical beginner's tutorial with Python code examples on WikiVersity. Partially written by one of the authors of the present software.
  * "Algebraic codes for data transmission", Blahut, Richard E., 2003, Cambridge university press. `Readable online on Google Books <https://books.google.fr/books?id=eQs2i-R9-oYC&lpg=PR11&ots=atCPQJm3OJ&dq=%22Algebraic%20codes%20for%20data%20transmission%22%2C%20Blahut%2C%20Richard%20E.%2C%202003%2C%20Cambridge%20university%20press.&lr&hl=fr&pg=PA193#v=onepage&q=%22Algebraic%20codes%20for%20data%20transmission%22,%20Blahut,%20Richard%20E.,%202003,%20Cambridge%20university%20press.&f=false>`_.


.. |Example| image:: https://raw.githubusercontent.com/lrq3000/pyFileFixity/master/tux-example.jpg
   :scale: 60 %
   :alt: Image corruption and repair example
.. |PyPI-Status| image:: https://img.shields.io/pypi/v/pyfilefixity.svg
   :target: https://pypi.org/project/pyfilefixity
.. |PyPI-Versions| image:: https://img.shields.io/pypi/pyversions/pyfilefixity.svg?logo=python&logoColor=white
   :target: https://pypi.org/project/pyfilefixity
.. |PyPI-Downloads| image:: https://img.shields.io/pypi/dm/pyfilefixity.svg?label=pypi%20downloads&logo=python&logoColor=white
   :target: https://pypi.org/project/pyfilefixity
.. |Build-Status| image:: https://github.com/lrq3000/pyFileFixity/actions/workflows/ci-build.yml/badge.svg?event=push
   :target: https://github.com/lrq3000/pyFileFixity/actions/workflows/ci-build.yml
.. |Coverage| image:: https://codecov.io/github/lrq3000/pyFileFixity/coverage.svg?branch=master
   :target: https://codecov.io/github/lrq3000/pyFileFixity?branch=master
