PyFileFixity Todo
=============

TODO
--------

000000000. Urgent bugfixes: code coverage is varying because unit test is non-deterministic somehow! Need to fix this issue! Maybe a difference between platforms (eg, of data encoding?) + Need to fix encoding error, see issue #7 on GitHub (and may be related to the previous point). See https://community.codecov.com/t/reported-change-in-coverage-when-no-code-changes-made/1346/9 and https://docs.codecov.com/docs/unexpected-coverage-changes

00000000. Rework routines with asyncio https://github.com/SuperFastPython/PythonAsyncioJumpStart

0000000. Type hinting and use mypyc to optimize without using Cython, or Codon (when it will work on Windows and switch to opensource in 2025-11-01)

000000. Implement a fast algorithm for large data encoding (and decoding), see [https://github.com/catid/leopard leopard-RS] for a FFT approach or [https://github.com/Bulat-Ziganshin/FastECC FastECC] for a NTT approach.

00000. Replace Gooey with pySimpleGUI for GUI handling.

0000. Implement robust mode, to skip folders/files that are inaccessible for the current user, eg, System Volume Information on Windows OSes.

000. Implement SIMD parallelization (process multiple messages at once) and Numpy. And fix ecc redundancy rate so we can use same coefficient for multiple messages. See the TODO below.

00. Implement fast matrix encoding in Reed-Solomon, see https://github.com/lrq3000/unireedsolomon/issues/2 and BackBlaze tutorial.

1. Parallelization of encoding: build a list of all files to encode in a multiprocessing.Queue() (or list or dict) to be multiprocessing safe, and then process different files in Pool, each time a job is launched, pop from the shared queue. Each worker will write in its own file, and in the end all files will be concatenated into one. This should speed-up processing, x8 with 8 cores thus we could reach about 10MB/s and thus get reasonable encoding time speed. Try to use [jug](https://github.com/luispedro/jug)! Sharing of data through filesystem, pure python and easy to use, seems like a perfect fit. Or [dask](http://dask.pydata.org/en/latest/) (pydata project, pandas authors).

1bis. Check if accentuated characters work. If not, use recwalk(unicode(rootfolderpath)) instead of recwalk(rootfolderpath)

2. hello world in ecc file header as a comment, so that user can detect Reed-Solomon parameters even if commandline arguments are forgotten (using half rate so that k and n is known: k = n/2).
Canonic format:

    ```
    ** Script name and version
    ** my-script.py --arg1 --arg2 --arg3
    ** Parameters of the ecc here.
    ** Hello world <ecc-here>
    <entry_marker>/path/to/my-first-file.txt<field_delim>231<field_delim><ecc-of-filepath><field_delim><ecc-of-size><field_delim><hash-of-chunk1><ecc-of-chunk1><hash-of-chunk2><ecc-of-chunk2> etc...
    <entry_marker>/path/to/my-first-file.txt<field_delim>231<field_delim><ecc-of-filepath><field_delim><ecc-of-size><field_delim><hash-of-chunk1><ecc-of-chunk1><hash-of-chunk2><ecc-of-chunk2> etc...
    ```

3. compute redundancy rate(n, k) and the opposite, and show in precomputation stats in header_ecc.py and structural_adaptive_ecc.py.
http://stackoverflow.com/questions/24421305/overhead-of-error-correcting-codes-as-the-error-rate-increases?rq=1
Difference between resiliency rate and redundancy rate: resiliency rate is the number of errors you can correct in the original message (ie: 0.3% means that you can correct 30% of your original message), while redundancy rate is the number of errors you can correct in the whole codeword (ie: 30% means that you can correct 30% over the original message + ecc symbols, thus if you just want to correct errors in the original message, it's a lot less than 30%). That's why resiliency rate can easily attain 100% (which means that you can correct errors in every symbols of the original message) and even beyond, while 100% is the unachievable limit of redundancy rate (because 100% means that you can correct errors in every symbols of the whole codeword, which would mean that you use only ecc symbols and no symbols from the original message at all, which is impossible since you need at least one original message's symbol to compute an ecc code, thus you can only attain 99.9...% at maximum).
4. eccman add a new method to decode more robustly: if decoding fails and k <= floor(n/2) then try to decode with erasures considering input as all erasures (useful for index backup, path strings, etc.). And inversely! If erasures enabled, then try without erasures (maybe too much false positives).
Put that as a new method in eccman which will call self.decode() and if self.check not ok and k <= n//2 then try erasures only!
5. replication_repair.py :
    * Use collections.counter() for the `hist` variable (or just keep it a dict? But counter should be more efficient, and can always try and except failsafe to dict if not available): https://docs.python.org/2/library/collections.html#collections.Counter
    * Last modification date: show a warning if not same last modif date? (but should be able to disable with cmdline argument).
    * Last modification date: allow to give more weight to the most recent files? Or even oldest files?
6. resiliency tester script:
    * add support for replication_repair.py simulation? (ie, automatically make duplicated folders and then run replication_repair.py)
7. multi-file support (with file recreation, even if can only be partially recovered, missing file will be replaced by null bytes on-the-fly)
if multi supplied, intra-fields "filepath" and "filesize" will be joined with "|" separator. The generation and decoding of intra-fields ecc does not change (it's still considered to be one field for eccman).
Weak spot is the number of files per ecc track, that's why it won't be stored in an intra-field, but supplied by user in commandline argument. This means that the number of files per ecc track will be fixed, if there's one missing then an empty file will be used (thus the existing files for this ecc track, the last ecc track, will be more resilient than necessary, but anyway it will impact the files with the lowest size overall given our clustering strategies so the overhead won't be much).
Two modes: simple and normal. Simple will just group together files (order by size) without trying to fill the gaps.
Normal: to-fill = dict toujours sorté descendant (highest first) et la key est la taille à remplir pour tel couple (cluster, groupe).
    * For each file:
        * If to-fill list is empty or file.size > first-key(to-fill):
            * Create cluster c with file in first group g1
            * Add to-fill[file.size].append([c, g2], [c, g3], ..., [c, gn])
        * Else:
            * ksize = first-key(to-fill)
            * c, g = to-fill[ksize].popitem(0)
            * Add file to cluster c in group g
            * nsize = ksize - file.size
            * if nsize > 0:
                * to-fill[nsize].append([c, g])
                * sort to-fill if not an automatic ordering structure
    * (Original note: Implement multi-files ecc, which would be a generalization of PAR2: set a new configurable parameter split_stream which would fetch the stream of characters from the specified number of files. We could for example set 3 to use 1/3 of characters from each 3 files, 10 to compose the message block from 10 different files, etc. This would allow to make an ecc file that could recreate lost files from files that are still available (this also fix a bit the issue of directory tree meta-data truncation).
    * Note: already done the algorithms in lib/aux_lib.py, only need to encode the list of files in the ecc file intra-fields (need to modify filepath and filesize intra-fields), and then use that to encode/decode properly by joining the blocks of each file.
8. Post stable release, and post on reddit and https://groups.google.com/forum/#!forum/digital-curation
9. Use six for Python 3 compatibility? (And in the future, try to avoid six and make really compatible code, or directly use [futurize](http://python-future.org/overview.html#automatic-conversion-to-py2-3-compatible-code) to generate a first Py3-compatible draft and then refine it manually).

10. (maybe) implement file_scraping option in header_ecc.py and structural_adaptive_ecc.py: at repair, walk through each files (instead of walking from the database entries), and check each database entry to see if the file corresponds to an ecc track: we try to decode each ecc block against the file, and if there's some number of ecc blocks that perfectly match the file, or can be repaired without any error, then we will know this is the correct ecc entry and we can even rename the file. The threshold could be the ratio of matching/repairable ecc blocks over the total number of ecc blocks. By default, ratio would be 100% (perfect match required to rename the file), but can be specified as commandline parameter (eg: --filescrape without value == 100%, --filescrape 50 == 50% threshold). Could also check by filesize. See: https://github.com/Parchive/par2cmdline#misnamed-and-incomplete-data-files
11. Branch coverage 100%
12. Python 3 compatibility (only after branch coverage 100% to ensure functionality remains the same)
13. (maybe) cauchy RS using Cython to interface with LongHair lib.
14. (maybe) hash with principle of locality (polynomial division remainder?)
15. (maybe) bruteforce decoding from locality hash (try every possible polynomials using chinese remainder theorem?)
simply generate all big ints that corresponds to the given remainder up to 2^8 poly and then check the one that corresponds to the md5 hash. Thus the ecc code will consists of: md5 hash + remainder + ecc for these to correct them in case of bug.
http://mathematica.stackexchange.com/questions/32586/implementation-of-the-polynomial-chinese-remainder-theorem
http://www.mathworks.com/matlabcentral/fileexchange/5841-chinese-remainder-theorem-for-polynomials
16. (maybe) Monte Carlo simulation for resiliency tester: https://www.livebusinesschat.com/smf/index.php?topic=5933.0


MAYBE
----------

- Append/remove: just make a list of files from db and compare against real file tree, then just remove entries inexistent, and append at the end the new files. Only if file size and checksum are the same, else remove file and append at the end.

- Filename recovery: compare against filesize: simply extract list of files as dict key and value = file size, then walk through real file tree and make similar db, reorganize both according to filesize, and do a 1-on-1 comparison of decreasing filesize: if one real file match a db filesize, then add it to the dict of correspondance db filename -> real filename. If multiple entries, ask user.

- Move from argparse to [argopt](https://github.com/casperdcl/argopt) (would probably be the best choice! Just need to make sure it would work with my AutoGooey wrapper) or [docopt](https://github.com/docopt/docopt) or [click](http://click.pocoo.org/) to generate a beautiful and more usable command-line interface (with clear modes, because right now the relevant options are not grouped together and it can be quite confusing).

- High priority: parallelize eccman.py to encode faster in a generic fashion (ie, using any codec). It would call n parallel instances of the ecc codec, to compute n ecc blocks in parallel. This should give us at least a 10x speedup (if compatible with PyPy, this would make us reach 10MB/s!).
maybe with: https://github.com/XericZephyr/Pythine ?
or maybe with [joblib](http://blog.rtwilson.com/my-top-5-new-python-modules-of-2015/comment-page-1/#comment-170352)?

- FFT to get O(nlogn) encoding instead of O(nk) (quadratic)? Like [this project](https://github.com/alexbeutel/Error-Correcting-Codes).

- Extend pyFileFixity to encode multiple characters into one, and then use higher galois fields like 2^16, 2^32 or even 2^128 (allows to be more resilient against huge, adversarial bursts): for example, instead of having one character ranging from value [0,255], we would have two characters encoded in one in range [0,65535] and then we could use GF(2^16) and encode blocks of 65535 characters instead of 255. This may also help us encode faster (since we would process bigger ecc blocks at once, but we'd have to see if the computational complexity of RS doesn't cancel this benefit...). We could also maybe use optimization tricks in: Luo, Jianqiang, et al. "Efficient software implementations of large finite fields GF (2 n) for secure storage applications." ACM Transactions on Storage (TOS) 8.1 (2012): 2.

- structure check for zip files? (Just check if we can open without any error. What kind of error if partially corrupted?).

- structure check for movies/video files using moviepy https://github.com/Zulko/moviepy ?

- structural_adaptive_ecc.py: --update "change/remove/add" (change will update ecc entries if changed, remove will remove if file is not present anymore, add will encode new files not already in ecc file). For all, use another ecc file: must be different from input ecc file (from which we will streamline read and output to the target ecc file only if meet conditions).

- Implement safety checks from Reed-Solomon Codes by Bernard Sklar : http://ptgmedia.pearsoncmg.com/images/art_sklar7_reed-solomon/elementLinks/art_sklar7_reed-solomon.pdf

- reed-solomon extension supporting insertions and deletions of characters in a message block (but it may not be very useful in our case, since mediums usually cannot insert nor delete characters... Should first see if storage mediums can be phase distortion channels or not.).

- High priority: implement list decoding instead of unique decoding when above the error-capacity of (n-k)/2 (called the Singleton Bound, see Adams, 2008): list decoding would then offer several possible messages to recover, instead of none, and it would be either up to the user to choose, or if we know the file format, we could use that information to know what kind of data and thus message we should choose via automatic heuristics. Note: it may not be useful for codes with a rate higher than 0.3. See: Folded Reed-Solomon Codes http://en.wikipedia.org/wiki/Folded_Reed%E2%80%93Solomon_code and http://en.wikipedia.org/wiki/Reed%E2%80%93Solomon_error_correction#Decoding_beyond_the_error-correction_bound and http://en.wikipedia.org/wiki/List_decoding and Guruswami, V.; Sudan, M. (September 1999), "Improved decoding of ReedSolomon codes and algebraic geometry codes", IEEE Transactions on Information Theory 45 (6): 17571767 and Koetter, Ralf; Vardy, Alexander (2003). "Algebraic soft-decision decoding of ReedSolomon codes". IEEE Transactions on Information Theory 49 (11): 28092825. and https://math.stackexchange.com/questions/93372/is-correcting-2-consecutive-errors-in-9-messages-from-gf26-by-turning-th?rq=1 and http://ocw.mit.edu/courses/electrical-engineering-and-computer-science/6-451-principles-of-digital-communication-ii-spring-2005/lecture-notes/chap8.pdf
See also the histogram approach in "Transform Techniques for Error Control Codes", Blahut, May 1979, IBM J. Res. Develop., Vol.23, No.3, http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.92.600&rep=rep1&type=pdf and Egorov, Sergey, and Garik Markarian. "Error Correction Beyond the Conventional Error Bound for Reed-Solomon Codes." JOURNAL OF ELECTRICAL ENGINEERING-BRATISLAVA- 54.11/12 (2003): 305-310. http://iris.elf.stuba.sk/JEEEC/data/pdf/11-12_103-05.pdf and Wu, Yingquan. "New list decoding algorithms for Reed-Solomon and BCH codes." Information Theory, 2007. ISIT 2007. IEEE International Symposium on. IEEE, 2007. and Kaltofen, Erich L., and Clément Pernet. "Sparse Polynomial Interpolation Codes and their decoding beyond half the minimal distance." arXiv preprint arXiv:1403.3594 (2014). and Egorov, Sergey, and Garik Markarian. "A modified Blahut algorithm for decoding Reed-Solomon codes beyond half the minimum distance." Mobile Future and Symposium on Trends in Communications, 2003. SympoTIC'03. Joint First Workshop on. IEEE, 2003.
A step-by-step conversion from BM to an interpolating list decoding can be found here: http://ita.ucsd.edu/workshop/06/papers/316.pdf "An Interpolation Algorithm for List Decoding of Reed-Solomon Codes", Kwankyu Lee and Michael E. O'Sullivan
Theoretical limits: Guruswami, Venkatesan, and Atri Rudra. "Limits to list decoding Reed-Solomon codes." Proceedings of the thirty-seventh annual ACM symposium on Theory of computing. ACM, 2005.
High speed algorithm for list decoding and complexity comparisons: https://hal.inria.fr/hal-00941435v2/document
Erasure + errors: http://www.researchgate.net/publication/224163900_High-speed_Re-encoder_Design_for_Algebraic_Soft-decision_Reed-Solomon_Decoding
A thesis with practical algorithms to implement list decoding efficiently: "Application of Computer Algebra in List Decoding", by Muhammad Foizul Islam Chowdhury, PhD Thesis, Jan 2014
FOUND bound: In 2001, Guruswami and Sudan published a random polynomial time algorithm that allowed decoding in the presence of up to n - sqrt(n*k) errors [8] [9]. See http://www.math.uci.edu/~mketi/research/advancementsummary.pdf "Reed-Solomon Error-correcting Codes - The Deep Hole Problem", by Matt Keti, Nov 2012 and V. Guruswami. List Decoding of Error-Correcting Codes. Springer-Verlag Berlin Heidelberg, 2004 for the detailed algorithm. This bound means that we overcome the bound more when n is big and k is low (max_block_size is high and resiliency_rate is also high). For example, with n=255 and k=n/2=127, we can correct 75 errors on symbols (characters) instead of 64! We gain 11 errors! In other words, we get a resiliency rate of 59% instead of 50% (9% more)! Also see http://anisette.ucs.louisiana.edu/Academic/Sciences/MATH/stage/puremath2011.pdf "LIST DECODING ALGORITHMS FOR REED-SOLOMON CODES", ITELHOMME FENE, MARLENE GONZALEZ, JESSICA JOHNSON, KAHNTINETTA PROUT, 2011
Also see the very interesting paper: "On the Locality of Codeword Symbols", by Parikshit Gopalan and Cheng Huang and Huseyin Simitci, 2011
Good intro: http://web.stanford.edu/class/ee392d/Chap8.pdf

- High priority: make a product code with interleaving, like Cross-Interleaved Reed-Solomon coding (CIRC) on optical discs? But how to define the interleaving? We could do another ecc with interleaving over the first ecc file? See http://en.wikipedia.org/wiki/Cross-interleaved_Reed%E2%80%93Solomon_coding and http://rscode.sourceforge.net/rs.html and http://en.wikipedia.org/wiki/Reed%E2%80%93Solomon_error_correction#Data_storage and also see the self-healing cube idea at https://blog.ethereum.org/2014/08/16/secret-sharing-erasure-coding-guide-aspiring-dropbox-decentralizer/. See also Error and Erasure Correction of Interleaved ReedSolomon Codes, Georg Schmidt, Vladimir R. Sidorenko, Martin Bossert, 2006 and http://www.usna.edu/Users/math/wdj/_files/documents/reed-sol.htm
"Interleaving is used to convert convolutional codes from random error correcters to burst error correcters.The basic idea behind the use of interleaved codes is to jumble symbols at the receiver. This leads to randomization of bursts of received errors which are closely located and we can then apply the analysis for random channel. Thus, the main function performed by the interleaver at transmitter is to alter the input symbol sequence. At the receiver, the deinterleaver will alter the received sequence to get back the original unaltered sequence at the transmitter." From Wikipedia: http://en.wikipedia.org/wiki/Burst_error-correcting_code . In other words, we could use an interleaver here to significantly increase the burst resilience (by encoding the ecc over multiple files instead of one, we multiply the n-k bound by the size of the files used) at the expense of files independence (meaning that we will need multiple files to decode one file, so it would hamper the partial recovery capability because files won't be independent from each other anymore).
For a nice technical description, see: http://isites.harvard.edu/fs/docs/icb.topic982877.files/Moon-%20Introduction%20to%20Reed%20Solomon%20Codes.pdf
An easy and practical way of achieving this goal would be to do something like the "byte-spreading" that is implemented in http://manpages.ubuntu.com/manpages/natty/man1/rsbep.1.html
Best resource: https://en.wikipedia.org/wiki/Talk:Reed%E2%80%93Solomon_error_correction#error_value_calculations_with_multi-layer_codes
"In the case of a multi-layer code like CIRC, it's usually faster to generate a matrix for the outer code correction. Consider the inner code to be the rows of a matrix, and the outer code to the columns. The rows are handled first, and then correction on the columns of all rows can be treated as erasure cases, multiplying the inverted locator matrix with each column's syndromes to do the correction. If an error occurs in a column, then the failing row (once determined) can be added to the row erasure list, a new inverted locator matrix generated and correction continued. Expansion of terms from the Forney algorithm can be used avoid having to actually invert a matrix."
http://web.stanford.edu/class/ee392d/Chap8.pdf

- Implement near-optimal decoders such as LDPC or turbo-codes. Near-optimal decoders are a bit less efficient than Reed-Solomn (they can recover fewer errors), but they are so much faster that it may be worth for huge datasets where the encoding computation time of Reed-Solomon is just impractical. Also another big advantage is that they are less prone to the cliff effect: this means that even if we can't correct the whole message because too much corruption, they may allow to partially correct it nevertheless.
Maybe use this python with numpy library (no compilation): https://github.com/veeresht/CommPy
Also this library includes interleavers, which may be interesting to be more resilient with RS too. However I hardly see how to interleave without the recovery file being less resilient to tampering (because if you interleave, you have to store this interleaving info somewhere, and it will probably be in the ecc recovery file, which will make it less resilient against corruption although the protected files will be more resilient thank's to interleaving...).
See also: http://web.eecs.utk.edu/~plank/plank/classes/cs560/560/notes/Erasure/2004-ICL.pdf
See also: http://static1.1.sqspcdn.com/static/f/679473/23654475/1381240807933/grcon13_perez_gsoc_ldpc.pdf?token=8zKywMTkqzPtiE8f5Y0ZwJe%2BJeQ%3D and the code in python at https://github.com/tracierenea/GNU-Radio-GSoC2013/tree/master/gr-ldpc/python
Cauchy Reed-Solomon in C: https://github.com/catid/longhair . Cauchy-RS and Vandermonde-RS are very interesting in that the encoding process assumes a code of RS(N, K) which results in N codewords of length N symbols each storing K symbols of data, being generated, that are then sent over an erasure channel. This means that, contrary to the currently implemented classical RS where we can correct n-k symbols, here we could correct N-K blocks of symbols! This is very interesting in case of burst correction, but in case of random errors (bits are often corrupted but not on a long run), this would be awful, because if we tamper one bit of just one symbal in at least N-K/2 blocks, we cannot correct anything. Thus, we would have to find a good balance for the block size, not setting one too long to avoid this kind of scenario, but long enough to maximize the recovery. The currently implemented RS is good enough for now, but Cauchy or Vandermonde RS could be very interesting alternatives for specific cases (mainly depending on the kind of erasures that can happen on your storage medium of choice, eg: for flash storage, I think we should avoid, but for optical mediums it could be very nice, and for HDD it would be good also but with a very small block size). Also see for optimal performance Cauchy RS: http://web.eecs.utk.edu/~plank/plank/papers/NCA-2006.pdf "Optimizing Cauchy Reed-Solomon Codes for Fault-Tolerant Network Storage Applications", Planck
Pure Python CRC module: https://github.com/tpircher/pycrc

- Auto detection of ecc file parameters (and ecc code parameters like primitive polynomial and generator polynomial). Of course, it will always be less efficient than just having the user set the correct parameters (because if the ecc file is tampered just a bit too much, the ecc parameters detection won't work), but it could still be useful. See:
    * "Automatic Recognition and Classification of Forward Error Correcting Codes" by Joseph Frederick Ziegler (2000), Master Thesis (with sourcecode in Matlab included in appendix or copied here: https://github.com/moreati/ziegler2000). http://ece.gmu.edu/crypto_resources/web_resources/theses/GMU_theses/Ziegler/Ziegler_Spring_2000.pdf
    * Zahedi, A., & Mohammad-Khani, G. R. (2012). "Reconstruction of a non-binary block code from an intercepted sequence with application to reed-solomon codes". IEICE TRANSACTIONS on Fundamentals of Electronics, Communications and Computer Sciences, 95(11), 1873-1880.
    * Lu Ouxin, Gan Lu and Liao Hongshu, 2015. "Blind Reconstruction of RS Code". Asian Journal of Applied Sciences, 8: 37-45. http://www.scialert.net/abstract/?doi=ajaps.2015.37.45
    * "The Dimension of Subcode-Subfields of Shortened Generalized Reed Solomon Codes", Fernando Hernando, Kyle Marshall, Michael E. O'Sullivan http://arxiv.org/abs/1108.5475

- Extend the RS codec universal architecture with any prime base? Chang, F. K., Lin, C. C., Chang, H. C., & Lee, C. Y. (2005, November). Universal architectures for Reed-Solomon error-and-erasure decoder. In Asian Solid-State Circuits Conference, 2005 (pp. 229-232). IEEE. http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.377.6275&rep=rep1&type=pdf

IDEAS AND STUFF
--------------------------

- Implement resilient algorithms and data structures for meta-data such as folders pointing to files? With the goal of interconnecting randomly multiple entries together so that finding one correct ecc entry may lead to another, even if the delimiters and entrymarker are corrupted! Use skip graphs or simple merkle trees or resilient dictionaries as in: https://www.imsc.res.in/~dsmeet/Francesco.pdf and Christiano, Paul, Erik D. Demaine, and Shaunak Kishore. "Lossless Fault-Tolerant Data Structures with Additive Overhead." Algorithms and Data Structures. Ed. Frank Dehne, John Iacono, & Jörg-Rüdiger Sack. LNCS Vol. 6844. Berlin, Heidelberg: Springer Berlin Heidelberg, 2011. 243254. Also see: Sean Quinlan and Sean Dorward built a content-addressed storage system called Venti http://research.swtch.com/backups and also sparse sets http://research.swtch.com/sparse
Some way to do that would be to make a virtual filesystem and copy the files into it, and bundle it with the ecc. This is the approach taken here: http://users.softlab.ntua.gr/~ttsiod/rsbep.html

- Important idea, maybe todo: implement cross ecc blocks recovery. To implement partial recovery of a file, we made the ecc file specification so that each message block is considered independent, and the ecc blocks thus are too. But we may add an info or construct the ecc in such a way that the previous ecc block may give some info about the next ecc block, or the next message block, but in a way that would incur no penalty if the previous ecc block is corrupted or unknown. Maybe using an overdeteremining both ecc blocks, thus linking them. I don't know exactly how to do, but the idea is to make a chain link from an ecc block to the next, so that we get some additional info for almost free which we could use either to better recover messages, or to recover corrupted ecc (either enhance the recovery process or the ecc file resiliency against corruption). A concrete way we may try would be to reuse the idea of QArt Codes modification so that we can modify the next ecc block to still be valid for its message but some of the coefficients will also be correct to repair the previous ecc block: first we compute the next ecc block for the next message block, and then we compute the ecc for the previous ecc block, then we tweak the next ecc block using QArt method to tweak it so that some coefficients match the ecc for the previous ecc block. This way, we have each ecc block able to repair both the corresponding message block, but also the previous ecc block, without any storage cost! (of course there is a computational cost, but we may be able to go beyond the repair limit of n-k just by some clever structural construction!). See http://research.swtch.com/qart and https://code.google.com/p/rsc/source/browse/qr by Russ Cox. It is also possible to add 2 characters to a RS code (so it's n+2) without modifying the code nor its redundancy: Reed-Solomon Codes by Bernard Sklar : http://ptgmedia.pearsoncmg.com/images/art_sklar7_reed-solomon/elementLinks/art_sklar7_reed-solomon.pdf
Also see: http://ocw.mit.edu/courses/electrical-engineering-and-computer-science/6-451-principles-of-digital-communication-ii-spring-2005/lecture-notes/chap8.pdf which says that the Singleton Bound can be understood as saying that we can freely specify the symbols in some coordinates, and then the remainder of the codeword is uniquely specified (Theorem 8.1).

- regular representation for polynomials over galois fields may be faster than current vectorial representation? http://mathworld.wolfram.com/FiniteField.html

- matrix implementation: https://www.backblaze.com/blog/reed-solomon/ and https://github.com/Backblaze/JavaReedSolomon

- NOTTODO: faster decoder, implement the Euclidian decoder instead of Berlekamp-Massey. They are both equivalent. However, Euclidian decoder could be implemented if there could be some significant gain (speedup or correction capacity). See "Efficient algorithms for decoding Reed-Solomon codes with erasures", by Todd Matee https://mthsc.clemson.edu/misc/MAM_2014/bmj9b.pdf, see also 2tn decoder of Blahut: Blahut, Richard E. "A universal Reed-Solomon decoder." IBM Journal of Research and Development 28.2 (1984): 150-158. http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.84.2084&rep=rep1&type=pdf and for a simple introduction to the euclidian algo (in fact it's called Sugiyama Algorithm for Solving Key Equation): http://web.ntpu.edu.tw/~yshan/BCH_decoding.pdf
Inversion-less berlekamp-massey in MatLab: https://groups.google.com/forum/message/raw?msg=comp.dsp/5BNwkCcvFbU/9duaEwX9sSAJ
Inversion-less BM algo: Chang, F. K., Lin, C. C., Chang, H. C., & Lee, C. Y. (2005, November). Universal architectures for Reed-Solomon error-and-erasure decoder. In Asian Solid-State Circuits Conference, 2005 (pp. 229-232). IEEE. http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.377.6275&rep=rep1&type=pdf
Easiest algorithm and enhanced inversion-less BM algo with full pseudo-code: High-Speed Architetures for Reed-Solomon Decoders Dilip V. Sarwate and Naresh R. Shanbhag http://www.ifp.illinois.edu/~sarwate/pubs/Sarwate01High.pdf
Faster than inversion-less BM: Truong, Trieu-Kien, Jyh-Horng Jeng, and T. C. Cheng. "A new decoding algorithm for correcting both erasures and errors of Reed-Solomon codes." Communications, IEEE Transactions on 51.3 (2003): 381-388.
Also see this marvelous implementation in OCaml which implements nearly all RS decoders, including errors-and-erasures decoding and works online! https://github.com/ujamjar/reedsolomon
The best bet I think is to implement the Time-Domain decoder, without Syndrome nor Chien Search computation (chien search is the slowest part), see Figure 7.13 (A time-domain BCH decoder) in Blahut, "Algebraic Codes for Data Transmission", 2003.
Lin's table interpretation of Berlekamp-Massey can also be very interesting, requiring only 2t additions and 2t multiplications: Lin, S.: An Introduction to Error-Correcting Codes. Prentice-Hall, Englewood Cliffs, New Jersey, 1970. and Lim, Raymond S. "A decoding procedure for the Reed-Solomon codes." (1978).

CONTINUE LATER
---------------------

What is listed below was already worked on, so it can be considered done, but I keep it here for reference in case someone in the future wants to enhance these points further.

- Integrate with https://github.com/Dans-labs/bit-recover ? (need to convert the perl script into python...). Note: from my own tests, it doesn't work so well as the author thinks it is, I couldn't even correct a single corruption... Or maybe I am using it the wrong way (but I used the test scripts included, with no modification. That's weird...).

- High priority: Speed optimize the Reed-Solomon library? (using Numpy or Cython? But I want to keep a pure python implementation available just in case, or make a Cython implementation that is also compatible with normal python). Use pprofile to check where to optimize first.

Note: PyPy works great, it really speeds things up a lot!

Note2: numpy does not support galois finite fields in polynomials (or in any other numpy construct in fact). So it may be hard to implement using numpy. Try Cython?
http://jeremykun.com/2014/03/13/programming-with-finite-fields/

Note3: some speed optimizations were done (like precomputing every polynomials for any k, so that a variable rate encoder such as in structural_adaptive_ecc.py won't be slowed down), the last big thing to optimize is `polynomial.py:__divmod__()` which is a recursive function (very bad in Python). Should try to flatten this out (in a __while__ or better in a __for__ loop), and then maybe convert to Cython.

Note4: maybe try to parallelize? The problem is that all CPU intensive work is done in classes's methods, and usually parallelization doesn't work on classes...

Note5: still need 10 times speedup in polynomial/ff operations to be reasonable, and 100 times speedup to be really useful for day-to-day. By lowering max_block_size, it becomes usable, but with a 10x speedup it should be really useable. Try to use a more efficient polynomial division algorithm ? Or implement in C/C++ directly (Boost Python?).
http://www.math.uzh.ch/?file&key1=23398
http://en.wikipedia.org/wiki/Horner's_method
http://en.wikipedia.org/wiki/Multiply%E2%80%93accumulate_operation#Fused_multiply.E2.80.93add

Note6: with latest implementations, we have a 100x speedup when using PyPy 2.5.0: on an Intel Core i7 M640 2.80GHz and 4GB RAM on a SSD hard disk, encoding speed is ~600kB/s with --ecc_algo 2, ~1.3MB/s with --ecc_algo 3 and if you set --max_block_size 150 --ecc_algo 3 you get ~1.5MB/s, which is quite correct (~2 hours to encode 10GB). Not bad! However if we could achieve a 10x more speed boost to attain 10MB/s, it would just be perfect! If anyone knows how to optimize with Cython, it would be a great help, because I can't squeeze enough juice out of that...

Note7: we could try to implement the optimizations here: http://research.swtch.com/field or use https://github.com/pjkundert/ezpwd-reed-solomon or Phil Karn's reedsolomon http://www.ka9q.net/code/fec/ with this wrapper https://repository.napa-wine.eu/svn/pulse/trunk/pulse/FEC/coder.py or Cauchy RS on OpenCL: http://www.bth.se/fou/cuppsats.nsf/all/bcb2fd16e55a96c2c1257c5e00666323/$file/BTH2013KARLSSON.pdf and here: http://hpi.de/fileadmin/user_upload/fachgebiete/meinel/papers/Trust_and_Security_Engineering/2013_Schnjakin_CSE.pdf (just init Gt matrices with Cauchy matrix instead of Vandermonde, and use xor instead of GFmul).

Note8: a very fast c++ implementation, with a Python Swig interface: https://github.com/pjkundert/ezpwd-reed-solomon
There are papers about an enhanced (number of multiplications and additions reduced) RS encoder. See: "Optimized Arithmetic for Reed-Solomon Encoders", Christof Paar, 1997 and "A Fast Algorithm for Encoding the (255,223) Reed-Solomon Code Over GF(2^8)", by R.L. Miller and T.K. Truong and I.S. Reed, 1980

Note9: new leads:

    * implement pure C using CFFI
    * Precomputed polynomial multiplication tables.
    * Discrete Q-adic Transform (or any other ring morphism) and perform computations on the resulting integers. See Dumas, Jean-Guillaume, Laurent Fousse, and Bruno Salvy. "Simultaneous modular reduction and Kronecker substitution for small finite fields." Journal of Symbolic Computation 46.7 (2011): 823-840.

    def dqt(poly, q=1000):
        integer = 0
        for i in xrange(len(poly)-1,-1, -1):
            integer += poly[i]*q**i
        return integer

    * Optimized polynomial modular reduction (instead of division, we just need the remainder for encoding). See Luo, Jianqiang, et al. "Efficient software implementations of large finite fields GF (2 n) for secure storage applications." ACM Transactions on Storage (TOS) 8.1 (2012): 2. and Kneevic, M., et al. "Modular Reduction in GF (2 n) without Pre-computational Phase." Arithmetic of Finite Fields. Springer Berlin Heidelberg, 2008. 77-87. and Wu, Huapeng. On computation of polynomial modular reduction. Technical report, Univ. of Waterloo, The Centre for applied cryptographic research, 2000.

Note10: the best, easiest way to attain > 10MB/s is to **parallelize** in eccman.py and/or the structural_adaptive_ecc.stream_compute_ecc_hash() and header_ecc.compute_ecc_hash functions: currently we are at max between 3MB/s and 5MB/s. With parallelized processing of several parts of the same file in an asynchroneous manner, we could not only multiply the speed by the number of cores (with 4 virtual cores on an Intel Duo, you'd get ~12MB/s) + the time spent in I/O trying to read from the file would be asynchroneous thus we would not wait for it anymore, and thus we could gain a huge speed increase here too. See http://nealhughes.net/parallelcomp/

Note11: Fastest Reed-Solomon encoder I have found, in pure Go! Over 1GB/s. https://github.com/klauspost/reedsolomon

------------------

LATEST TODO 2017

ECC PYFILEFIXITY FASTER:

SUMMARY:

* Use PyPy 5 (with --jit vec=1 if also using numpy)
* Parallel execution on multiple blocks to get more in memory + IKJ algorithm: apply generator polynomial coefficient on ALL messages in same loop! Then go to 2nd coefficient. WARNING: works only if all messages have same resiliency! Better to compute faster AND then have more resiliency for all! At worst, can just save more resiliency for header, but the rest should be stable!
* Parallel calculation of polynomial division remainder: since XOR is commutative and associative, it does NOT matter which order is used, so can stupidly parallelize the polynomial division in GF. See this link (and other optimizations, should be applicable, particularly deferred message XORing): https://en.wikipedia.org/wiki/Computation_of_cyclic_redundancy_checks
* Numpy to process parallel messages by broadcasting: https://stackoverflow.com/questions/19278313/numpy-matrix-multiplication-with-custom-dot-product
* Erasure detection with orthogonal hash and/or use [Hamming distance](http://users.cs.fiu.edu/~downeyt/cop3402/hamming.html) (should be fast since only XOR and should give same error detection as number of hash symbols) or CRC as error detection (to lower k and thus computation time) - also CRC is much faster than other hashing algos to compute. For CRC [see this](https://groups.google.com/forum/#!msg/alt.sources/dBNqgU1rFYc/A32HmbL9GgAJ) and [this](https://rosettacode.org/wiki/CRC-32#Python) and [xxHash as an alternative](https://cyan4973.github.io/xxHash/). Can also use any CRC library but implement [One-Pass Checking](https://en.wikipedia.org/wiki/Computation_of_cyclic_redundancy_checks#One-pass_checking) to check the syndrome (just use message+CRC and compute CRC over all). And [this](https://en.wikipedia.org/wiki/Mathematics_of_cyclic_redundancy_checks#Error_detection_strength) for best polynomial choice. Only [single bit error location](https://stackoverflow.com/questions/24847138/how-can-the-crc-checksum-give-the-position-where-the-error-occured)? Not interesting in that case... Because a hash can find any bit error, there is no bound contrary to CRC!
* After numpy parallelized implementation: Try to use Intel Distribution for Python
* Implement Hybridization horizontal/vertical coding (by allowing to form messages from multiple files instead of just one)
* Finish new version with simplified names and Py3 support
* Try to optimize rs_generator_poly by avoiding polynomial multiplication but directly multiply in a single loop the same coefficient: reuse prime polynomial generator sanity check loop?
* Port 16bits RSC support from test code to master
* Later: integrate and potentially port NTT into pure python from Bulat's FastECC

FULL LOG:
* read how par2 did it (quickpar, multipar) or reed solomon on RAID
* BEST: the secret to PAR2 speed is to parallelize to a maximum: at instruction level by using SIMD (so can bitwise XOR lots of bits, up to 128 I think or even more) and then by usng horizontal coding because can fetch source bytes from lots of different files in parallel (and compute their blocks too in parallel)!

* TODO:

    000. Intel Distribution for Python: https://software.intel.com/en-us/distribution-for-python
    http://www.techenablement.com/orders-magnitude-performance-intel-distribution-python/
    Intel Vtune
    http://zibi.bids.berkeley.edu:7001/download/7
    Install IDP on Anaconda: http://www.infoworld.com/article/3187484/software/how-does-a-20x-speed-up-in-python-grab-you.html
    00. BEST: Numpy + IDP (Intel Distribution for Python) + Parallel execution on multiple blocks to get more in memory + Custom matrix dot product by broadcasting + Erasure detection with orthogonal hash (to lower k and thus computation time):
    https://stackoverflow.com/questions/19278313/numpy-matrix-multiplication-with-custom-dot-product
    0. SIMD IS POSSIBLE with PYPY4!!! See how to implement that! Other name for SIMD: vectorization!!!
    --jit vec=1
    https://morepypy.blogspot.be/2015/10/automatic-simd-vectorization-support-in.html
    Or use NumPyPy?
    BEST: http://ipython-books.github.io/featured-01/
    wmic cpu get L2CacheSize, L2CacheSpeed, L3CacheSize, L3CacheSpeed
    Run at 6MB/s!!! @python.exe structural_adaptive_ecc.py -i "folderimages" -d "ecc.txt" -l "log.txt" -r1 0.1 -r2 0.05 -r3 0.03 -g -f -v --ecc_algo 4 --max_block_size 80
    1. Implement parallelization, to compute multiple ECC in parallel, will speed up a LOT (because parallel calculation + reading more from the file so less hard disk fetching)
    BETTER to do parallelization on one file rather than on multiple files (because here we also speed up disk caching).
    BEST IMPLEMENTATION: provide all messages to the encode function, and apply the same coefficient XOR to ALL messages i-th byte at once! This should be automatically optimized by SIMD in PYPY4! But can also parallelize! Can do this for a HUGE set of blocks!
    see for inspiration: https://stackoverflow.com/questions/15992630/fast-small-and-repetitive-matrix-multiplication-in-python
    Alternative: CUDA! http://numba.pydata.org/numba-doc/dev/cuda/examples.html
    By using IKJ algo + PYPY, should be within 5x slower than numpy! (without BLAS obviously, but then it should still be 50x slower at least than C++...): https://martin-thoma.com/matrix-multiplication-python-java-cpp/
    and this: http://code.activestate.com/recipes/121574-matrix-vector-multiplication/
    simple matrix multiply pure python: https://www.programiz.com/python-programming/examples/multiply-matrix
    TRY: cpmoptimize: https://kukuruku.co/post/automatic-algorithms-optimization-via-fast-matrix-exponentiation/
    Can also use PyPy Vec: http://pypyvecopt.blogspot.be/2015/08/gsoc-vec-little-brother-of-numpy-array.html
    2. Double buffering: thread to write to ecc file instead of waiting, so can start next ECC calculation asap.
    python -m TBB <your>.py
    http://www.techenablement.com/orders-magnitude-performance-intel-distribution-python/
    3. Hybrid/horizontal scheme: allow to use multiple files as input. This should allow to be PAR-like if using k files as input, or  hybrid if using bigger blocks.
    4. for loops instead of while: for gf multiply, it's the number of bytes
    5. NTT maybe if can implement it fast (and if it's only XOR, would be very nice).
    6. SIMD in numpypy?
    http://www.complang.tuwien.ac.at/kps2015/proceedings/KPS_2015_submission_8.pdf
    https://github.com/planrich/pypy-simd-benchmark
    7. Orthogonal hashing to enable erasure correction: Implement another scheme for hashing: per file's blocks so we can tag these blocks of bytes as erasures. This is less precise because some bytes will be OK but it will double the recovery rate, so it is a good additional technique. Or in my case, should do per multiple files, or hash of i-th byte per each block, something that is orthogonal to the ecc I use.
    8. Try to implement Plank matrix multiplication, maybe will be faster for same result? But need to check if equivalent!
    UNDERSTOOD: using generator matrices (instead of polynomial), we can then inverse, because need to be squared. Then can implement matrix multiplication, which is a bit faster than polynomial division. Then, normally we should multiply by inverse of generator matrix to divide, but since anyway at decoding we will use the inverse, we can inverse at this moment (thus it will be easier to get a square matrix because we just need a k x k matrix, can remove superfluous values). Big advantage is then that SIMD will be effective and can do all matrix multiplication and factoring optimizations like micro slicing etc.
    BESTTUTO with EXAMPLE!: https://people.cs.clemson.edu/~westall/851/rs-code.pdf
    ask on StackExchange! Because matrix multiplication = convolution normally, not deconvolution!
    Also deconvolution = matrix multiplication of inverse = polynomial division?
    https://web.stanford.edu/class/ee387/handouts/notes09.pdf
    OR IIR/FIR in pure python if simple enough! see audiolazy or https://rosettacode.org/wiki/Apply_a_digitial_filter_(direct_form_II_transposed)#Perl_6
    https://stackoverflow.com/questions/19839539/how-to-get-faster-code-than-numpy-dot-for-matrix-multiplication
    mtimesx : MATLAB multidim matrix multiply: https://nl.mathworks.com/matlabcentral/fileexchange/25977-mtimesx-fast-matrix-multiply-with-multi-dimensional-support
    9. Try Julia? https://news.ycombinator.com/item?id=7110858
    Also MIT course on Julia
    10. Tinyarrays to reimplement fast GF operations? Or GF-complete package (modified by ParPar)?
* Migrate to erasure detection? How can we encode 4KB blocks instead of 4 bytes?
* Fast vandermonde/cauchy matrix multiplication (so will get SIMD/MMX optimization by parallelization so will speed up by 2**c_exp!)
simply numpy.vander([2, 4, 8, 16, etc.], N=256, increasing=True)
https://github.com/animetosho/ParPar
BEST: https://www.livebusinesschat.com/smf/index.php?topic=5521.0
https://docs.scipy.org/doc/numpy/reference/generated/numpy.vander.html
https://docs.scipy.org/doc/numpy-1.10.0/reference/generated/numpy.polynomial.polynomial.polyvander.html
ALSO: RS encoding = polynomial interpolation: FastECC project + https://jyyuan.wordpress.com/2014/01/02/polynomial-interpolation-using-vandermonde-matrix-and-least-squares/
does it mean we can use a regression to find the polynomial interpolation?
block RS design (unlimited bytes per block!) AND IT'S RS 8bits=256!!!!: https://github.com/catid/longhair
another tuto block design: http://cgi.di.uoa.gr/~ad/M155/Papers/RS-Tutorial.pdf
DECODING: https://www.backblaze.com/blog/reed-solomon/
https://www.youtube.com/watch?v=jgO09opx56o
BEST: Reliability and Power-Efficiency in Erasure-Coded Storage Systems - Kevin M Greenan + ref 18 for Cauchy reed solo
BEST PYTHON matrix RS: http://web.mit.edu/~emin/www.old/source_code/py_ecc/
BESTTUTO: http://web.eecs.utk.edu/~plank/plank/papers/2013-02-11-FAST-Tutorial.pdf
this is called: horizontal coding (compared to what I did that is vertical coding). Big advantage: can parallelize because each parity file can be computed separately. http://web.eecs.utk.edu/~plank/plank/papers/2013-02-11-FAST-Tutorial.pdf
My approach is non-systematic (ecc separated) vertical coding.
BESTTUTO for encoding complexity and decoding: https://www.ietf.org/rfc/rfc5510.txt
so even if we have more than k, we need to reduce to k elements! To get a square k-k matrix that is invertible!
speed tweaks: https://github.com/animetosho/ParPar/blob/master/xor_depends/info.md
* BESTTUTO: fast galos field multiplication in python: http://writes.co.de/2014/01/21/bitwise_galois/
BESTTUTO: irreducible polynomials = prime numbers powers of 2 (which is not possible outside of GF!): http://lemire.me/blog/2015/10/26/crazily-fast-hashing-with-carry-less-multiplications/
* For fast calculation, can also use SIMD=parallel computing: http://www.kaymgee.com/Kevin_Greenan/Publications_files/plank-fast2013.pdf
* lowering max_block_size to 100 or 80 speeds up! + lower resilience rate to 0.05
* implement CRC32 to error location detect, so increases resilence rate by 2x!
* FIR and IIR in Python: https://jyyuan.wordpress.com/2014/02/27/finite-impulse-response-fir-digital-filters/
* Note that the codec is specialized for the m = 1 case and runs very quickly. Due to a happy coincidence the first recovery block is always just an XOR of all the original data, so you can use this codec instead of doing that manually.
always true if fcr=0 : https://stackoverflow.com/questions/44117632/is-the-first-ecc-of-reed-solomon-always-the-same-as-xor
https://github.com/catid/longhair
* implement support for cpp libs such as longhair or fastecc (when it will be done) or wirehair or BETTER: https://github.com/catid/cm256
* BEST NTT tuto for RS with examples!
https://tmo.jpl.nasa.gov/progress_report2/42-35/35K.PDF - The fast decoding of reed-solomon codes with number theoretic transform by Reed et al
* multidim: https://www.youtube.com/watch?v=1_X-7BgHbE0
* implement micro slice optimization + double buffering? (saving ecc+hash into file in a thread meanwhile launching next calculation?): https://www.livebusinesschat.com/smf/index.php?topic=5877.0
* IDEA: since 1st ECC symbol always XOR of input message symbols, can use it for quick and dirty error detection! Without CRC!
* py_ecc approach: horizontal coding but per file: each symbol is stored in a different file. So ecc1 codes all first ecc symbol etc. This is nice because then we have multiple ecc files. We can generalize to multiple files by two ways: either PAR1 like by doing 1 character of each file, so k = number of files, OR do vertical coding by doing k = number of blocks for one file, and the first ecc is always stored in first ECC file, second ecc in 2nd ecc file, etc. And we append to the same ecc files for all files. This way, the ecc files will be as big as there are many files, but no limit to the number of files, and allow partial recovery! But disadvantage is that there is no interleaving and no file recreation (except if resiliency rate at least 25%, then it's possible, but then ecc files as big as the input files!). What about CD-ROM reed-solomon? Does it allow both?
NO: PAR approach allows partial reconstruction, because can reconstruct only i-th message which can be tampered differently from j-th message (ecc files missing in j-th for example).
* Maximum likelihood decoding: https://www.gaussianwaves.com/2010/01/maximum-likelihood-decoding-2/
