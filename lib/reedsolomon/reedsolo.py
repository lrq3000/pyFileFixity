"""
Modification notes by rotorgit 2/3/2015:
- made the following changes to reedsolo by Tomer Filiba (TF) in order
    to support ADSB UAT FEC standard as specified in:
    http://adsb.tc.faa.gov/WG5_Meetings/Meeting27/UAT-DO-282B-FRAC.pdf
- TF code is based on wikiversity RS code, so the mods are applicable there
    as well
- there were two changes needed to support ADSB UAT FEC decoding:
    1. non-zero "first consecutive root" (fcr): implicitly hard-coded as
    fcr=0 in previous version, needed fcr=120 for ADSB UAT
    2. "primitive polynomial": hard-coded as 0x11d in previous version,
    needed 0x187 for ADSB UAT
- both above params were hard-coded and are now user-definable (during
    class instantiation), with defaults equal to old values to
    prevent breakage of existing code
- there are many online resources for rs, but the best (most practical)
    for me was:
    http://downloads.bbc.co.uk/rd/pubs/whp/whp-pdf-files/WHP031.pdf
- as noted above, the wikiversity discussion and examples ignore/skip
    the critical features that must be modified for ADSB UAT support

Reed Solomon
============

A pure-python `Reed Solomon <http://en.wikipedia.org/wiki/Reed%E2%80%93Solomon_error_correction>`_
encoder/decoder, based on the wonderful tutorial at
`wikiversity <http://en.wikiversity.org/wiki/Reed%E2%80%93Solomon_codes_for_coders>`_,
written by "Bobmath".

I only consolidated the code a little and added exceptions and a simple API.
To my understanding, the algorithm can correct up to ``nsym/2`` of the errors in
the message, where ``nsym`` is the number of bytes in the error correction code (ECC).
The code should work on pretty much any reasonable version of python (2.4-3.2),
but I'm only testing on 2.5-3.2.

.. note::
   I claim no authorship of the code, and take no responsibility for the correctness
   of the algorithm. It's way too much finite-field algebra for me :)

   I've released this package as I needed an ECC codec for another project I'm working on,
   and I couldn't find anything on the web (that still works).

   The algorithm itself can handle messages up to 255 bytes, including the ECC bytes. The
   ``RSCodec`` class will split longer messages into chunks and encode/decode them separately;
   it shouldn't make a difference from an API perspective.

::

    >>> rs = RSCodec(10)
    >>> rs.encode([1,2,3,4])
    b'\x01\x02\x03\x04,\x9d\x1c+=\xf8h\xfa\x98M'
    >>> rs.encode(b'hello world')
    b'hello world\xed%T\xc4\xfd\xfd\x89\xf3\xa8\xaa'
    >>> rs.decode(b'hello world\xed%T\xc4\xfd\xfd\x89\xf3\xa8\xaa')
    b'hello world'
    >>> rs.decode(b'heXlo worXd\xed%T\xc4\xfdX\x89\xf3\xa8\xaa')     # 3 errors
    b'hello world'
    >>> rs.decode(b'hXXXo worXd\xed%T\xc4\xfdX\x89\xf3\xa8\xaa')     # 5 errors
    b'hello world'
    >>> rs.decode(b'hXXXo worXd\xed%T\xc4\xfdXX\xf3\xa8\xaa')        # 6 errors - fail
    Traceback (most recent call last):
      ...
    ReedSolomonError: Could not locate error

    >>> rs = RSCodec(12)
    >>> rs.encode(b'hello world')
    b'hello world?Ay\xb2\xbc\xdc\x01q\xb9\xe3\xe2='
    >>> rs.decode(b'hello worXXXXy\xb2XX\x01q\xb9\xe3\xe2=')         # 6 errors - ok
    b'hello world'
"""

import itertools

try:
    bytearray
except NameError:
    from array import array
    def bytearray(obj = 0, encoding = "latin-1"):
        if isinstance(obj, str):
            obj = [ord(ch) for ch in obj.encode("latin-1")]
        elif isinstance(obj, int):
            obj = [0] * obj
        return array("B", obj)


class ReedSolomonError(Exception):
    pass

gf_exp = [1] * 512
gf_log = [0] * 256

def init_tables(prim, x=1):
    global gf_exp, gf_log
    gf_exp = [1] * 512
    gf_log = [0] * 256
    for i in range(1, 255):
        x <<= 1
        if x & 0x100:
            x ^= prim
        gf_exp[i] = x
        gf_log[x] = i
    for i in range(255, 512):
        gf_exp[i] = gf_exp[i - 255]
    return [gf_log, gf_exp]

def init_tables_base3():
    global gf_exp, gf_log
    # Exponent table for 3, a generator for GF(256)
    gf_exp = [1, 3, 5, 15, 17, 51, 85, 255, 26, 46, 114, 150, 161, 248, 19,
        53, 95, 225, 56, 72, 216, 115, 149, 164, 247, 2, 6, 10, 30, 34,
        102, 170, 229, 52, 92, 228, 55, 89, 235, 38, 106, 190, 217, 112,
        144, 171, 230, 49, 83, 245, 4, 12, 20, 60, 68, 204, 79, 209, 104,
        184, 211, 110, 178, 205, 76, 212, 103, 169, 224, 59, 77, 215, 98,
        166, 241, 8, 24, 40, 120, 136, 131, 158, 185, 208, 107, 189, 220,
        127, 129, 152, 179, 206, 73, 219, 118, 154, 181, 196, 87, 249, 16,
        48, 80, 240, 11, 29, 39, 105, 187, 214, 97, 163, 254, 25, 43, 125,
        135, 146, 173, 236, 47, 113, 147, 174, 233, 32, 96, 160, 251, 22,
        58, 78, 210, 109, 183, 194, 93, 231, 50, 86, 250, 21, 63, 65, 195,
        94, 226, 61, 71, 201, 64, 192, 91, 237, 44, 116, 156, 191, 218,
        117, 159, 186, 213, 100, 172, 239, 42, 126, 130, 157, 188, 223,
        122, 142, 137, 128, 155, 182, 193, 88, 232, 35, 101, 175, 234, 37,
        111, 177, 200, 67, 197, 84, 252, 31, 33, 99, 165, 244, 7, 9, 27,
        45, 119, 153, 176, 203, 70, 202, 69, 207, 74, 222, 121, 139, 134,
        145, 168, 227, 62, 66, 198, 81, 243, 14, 18, 54, 90, 238, 41, 123,
        141, 140, 143, 138, 133, 148, 167, 242, 13, 23, 57, 75, 221, 124,
        132, 151, 162, 253, 28, 36, 108, 180, 199, 82, 246, 1] * 2

    # Logarithm table, base 3
    gf_log = [None, 0, 25, 1, 50, 2, 26, 198, 75, 199, 27, 104, 51, 238, 223,
            3, 100, 4, 224, 14, 52, 141, 129, 239, 76, 113, 8, 200, 248, 105,
            28, 193, 125, 194, 29, 181, 249, 185, 39, 106, 77, 228, 166, 114,
            154, 201, 9, 120, 101, 47, 138, 5, 33, 15, 225, 36, 18, 240, 130,
            69, 53, 147, 218, 142, 150, 143, 219, 189, 54, 208, 206, 148, 19,
            92, 210, 241, 64, 70, 131, 56, 102, 221, 253, 48, 191, 6, 139, 98,
            179, 37, 226, 152, 34, 136, 145, 16, 126, 110, 72, 195, 163, 182,
            30, 66, 58, 107, 40, 84, 250, 133, 61, 186, 43, 121, 10, 21, 155,
            159, 94, 202, 78, 212, 172, 229, 243, 115, 167, 87, 175, 88, 168,
            80, 244, 234, 214, 116, 79, 174, 233, 213, 231, 230, 173, 232, 44,
            215, 117, 122, 235, 22, 11, 245, 89, 203, 95, 176, 156, 169, 81,
            160, 127, 12, 246, 111, 23, 196, 73, 236, 216, 67, 31, 45, 164,
            118, 123, 183, 204, 187, 62, 90, 251, 96, 177, 134, 59, 82, 161,
            108, 170, 85, 41, 157, 151, 178, 135, 144, 97, 190, 220, 252, 188,
            149, 207, 205, 55, 63, 91, 209, 83, 57, 132, 60, 65, 162, 109, 71,
            20, 42, 158, 93, 86, 242, 211, 171, 68, 17, 146, 217, 35, 32, 46,
            137, 180, 124, 184, 38, 119, 153, 227, 165, 103, 74, 237, 222, 197,
            49, 254, 24, 13, 99, 140, 128, 192, 247, 112, 7]
    return [gf_log, gf_exp]

def gf_add(x, y):
    return x ^ y

def gf_neg(x):
    return x

def gf_inverse(x):
    return gf_exp[255 - gf_log[x]] # gf_inverse(x) == gf_div(1, x)

def gf_mul(x, y):
    if x == 0 or y == 0:
        return 0
    return gf_exp[(gf_log[x] + gf_log[y]) % 255]

def gf_div(x, y):
    if y == 0:
        raise ZeroDivisionError()
    if x == 0:
        return 0
    return gf_exp[(gf_log[x] + 255 - gf_log[y]) % 255]

def gf_pow(x, power):
    return gf_exp[(gf_log[x] * power) % 255]

def gf_poly_scale(p, x):
    return [gf_mul(p[i], x) for i in range(0, len(p))]

def gf_poly_add(p, q):
    r = [0] * max(len(p), len(q))
    for i in range(0, len(p)):
        r[i + len(r) - len(p)] = p[i]
    for i in range(0, len(q)):
        r[i + len(r) - len(q)] ^= q[i]
    return r

def gf_poly_mul(p, q):
    r = [0] * (len(p) + len(q) - 1)
    for j in range(0, len(q)):
        for i in range(0, len(p)):
            r[i + j] ^= gf_mul(p[i], q[j])
    return r

def gf_poly_divmod(dividend, divisor, nsym):
    '''Fast polynomial division by using Synthetic division (Horner's method)? Returns only the quotient (no remainder).'''
    msg_out = [0] * (len(dividend) + nsym)
    msg_out[:len(dividend)] = dividend
    for i in range(0, len(dividend)):
        coef = msg_out[i]
        if coef != 0:
            for j in range(0, len(divisor)):
                msg_out[i + j] ^= gf_mul(divisor[j], coef)
    return msg_out[len(dividend):]

def gf_poly_eval(p, x):
    y = p[0]
    for i in range(1, len(p)):
        y = gf_mul(y, x) ^ p[i]
    return y

def rs_generator_poly(nsym, fcr=0):
    g = [1]
    for i in range(fcr, fcr+nsym):
        g = gf_poly_mul(g, [1, gf_exp[i]])
    return g

def rs_generator_poly_base3(nsize, fcr=0):
    g_all = {}
    g = [1]
    g_all[0] = g_all[1] = g
    for i in range(fcr+1, fcr+nsize+1):
        g = gf_poly_mul(g, [1, gf_pow(3, i)])
        g_all[nsize-i] = g
    return g_all

def rs_encode_msg(msg_in, nsym, fcr=0, gen=None):
    if len(msg_in) + nsym > 255: raise ValueError("message too long")
    if gen is None: gen = rs_generator_poly(nsym, fcr)
    msg_out = bytearray(len(msg_in) + nsym)
    msg_out[:len(msg_in)] = msg_in
    for i in range(0, len(msg_in)):
        coef = msg_out[i]
        if coef != 0: # optimization, avoid computing something useless
            for j in range(0, len(gen)):
                if gen[j] != 0: msg_out[i + j] ^= gf_exp[(gf_log[gen[j]] + gf_log[coef])] # optimization, equivalent to gf_mul(gen[j], coef)
    msg_out[:len(msg_in)] = msg_in
    return msg_out

def rs_calc_syndromes_base3(msg, nsym, fcr=0):
    s = [0]
    s.extend([gf_poly_eval(msg, gf_pow(3, i)) for i in xrange(fcr+1, fcr+nsym+1)])
    return s

def rs_calc_syndromes(msg, nsym, fcr=0):
    return [gf_poly_eval(msg, gf_exp[i]) for i in range(fcr, fcr+nsym)]

def rs_correct_errata(msg_in, synd, pos, fcr=0):
    msg = list(msg_in)
    # calculate error locator polynomial using Forney algorithm
    q = [1]
    for i in range(0, len(pos)):
        x = gf_exp[len(msg) - 1 - pos[i]]
        q = gf_poly_mul(q, [x, 1])
    # calculate error evaluator polynomial
    p = synd[0:len(pos)]
    p.reverse()
    p = gf_poly_mul(p, q)
    p = p[len(p) - len(pos):len(p)]
    # formal derivative of error locator eliminates even terms
    q = q[len(q) & 1:len(q):2]
    # compute corrections
    for i in range(0, len(pos)):
        x = gf_exp[pos[i] + 256 - len(msg)]
        exp = ((len(msg) - 1 - pos[i])*(1 - fcr)) % 255
        xp = gf_exp[exp]
        y = gf_mul(gf_poly_eval(p, x), xp)
        z = gf_poly_eval(q, gf_mul(x, x))
        msg[pos[i]] ^= gf_div(y, z)
    return msg

def rs_correct_errata_base3(nsym, msg, synd, err_pos, err_loc):
    # complete chien search to get the error location polynomial X from the error positions in err_pos
    X = []
    for i in range(0, len(err_pos)):
        l = 255 - err_pos[i]
        X.append( gf_pow(3, -l) )
    Y = []
    s = nsym // 2
    for l, Xl in enumerate(X):
        # Compute the first part of Yl
        Yl = gf_pow(Xl,s)
        Yl = gf_mul( Yl, gf_poly_eval(err_loc, gf_inverse(Xl)) )
        Yl = gf_mul( Yl, gf_inverse(Xl) )

        # Compute the sequence product and multiply its inverse in
        prod = 1
        for ji in xrange(s):
            if ji == l:
                continue
            if ji < len(X):
                Xj = X[ji]
            else:
                Xj = 0
            prod = gf_mul(prod, gf_add(Xl, Xj))
        Yl = gf_mul(Yl, gf_inverse(prod))
        Y.append(Yl)

    # Put the error and locations together to form the error polynomial
    Elist = []
    for i in xrange(len(msg)):
        if i in err_pos:
            Elist.append(Y[err_pos.index(i)])
        else:
            Elist.append(0)
    E = Elist[::-1]

    # And we get our message corrected!
    c = gf_poly_add(msg, E)
    return c

def rs_gen_error_poly(synd):
    # find error locator polynomial with Berlekamp-Massey algorithm
    # TODO: try to also return the err_loc (error locator = omega in brownanrs library) for base3 decoding to work
    err_poly = [1] # This is the main variable we want to fill, also called sigma in other notations
    old_poly = [1]
    for i in range(0, len(synd)):
        old_poly.append(0)
        delta = synd[i]
        for j in range(1, len(err_poly)):
            delta ^= gf_mul(err_poly[len(err_poly) - 1 - j], synd[i - j])
        if delta != 0:
            if len(old_poly) > len(err_poly):
                new_poly = gf_poly_scale(old_poly, delta)
                old_poly = gf_poly_scale(err_poly, gf_inverse(delta)) # effectively we are doing err_poly * 1/delta = err_poly // delta
                err_poly = new_poly
            err_poly = gf_poly_add(err_poly, gf_poly_scale(old_poly, delta))

    err_poly = list(itertools.dropwhile(lambda x: x == 0, err_poly)) # drop leading 0s, else errs will not be of the correct size
    errs = len(err_poly) - 1
    if errs * 2 > len(synd):
        raise ReedSolomonError("Too many errors to correct")
    return err_poly

def rs_find_errors(err_poly, nmess):
    errs = len(err_poly) - 1
    # find zeros of error polynomial by bruteforce trial, this is a sort of Chien's search (but less efficient, Chien's search is a way to evaluate the polynomial such that each evaluation only takes constant time).
    err_pos = []
    for i in range(0, nmess):
        if gf_poly_eval(err_poly, gf_exp[255 - i]) == 0: # It's a 0? Bingo, it's a root of the error locator polynomial, in other terms this is the location of an error
            err_pos.append(nmess - 1 - i)
    if len(err_pos) != errs:
        return None    # couldn't find error locations
    return err_pos

def rs_find_errors_base3(err_poly):
    errs = len(err_poly) - 1
    # find zeros of error polynomial by bruteforce trial, this is a sort of Chien's search (but less efficient, Chien's search is a way to evaluate the polynomial such that each evaluation only takes constant time).
    err_pos = []
    for i in range(1, 256):
        if gf_poly_eval(err_poly, gf_pow(3, i)) == 0: # It's a 0? Bingo, it's a root of the error locator polynomial, in other terms this is the location of an error
            err_pos.append(255 - i)
    if len(err_pos) != errs:
        return None    # couldn't find error locations
    return err_pos

def rs_forney_syndromes(synd, pos, nmess):
    # Compute Forney syndromes, which is kind of an enhanced version of the other calculation of syndromes. Do not confuse this with Forney algorithm, which allows to correct the message based on the location of errors.
    fsynd = list(synd)      # make a copy
    for i in range(0, len(pos)):
        x = gf_exp[nmess - 1 - pos[i]]
        for i in range(0, len(fsynd) - 1):
            fsynd[i] = gf_mul(fsynd[i], x) ^ fsynd[i + 1]
        fsynd.pop()
    return fsynd

def rs_correct_msg(msg_in, nsym, fcr=0):
    if len(msg_in) > 255:
        raise ValueError("message too long")
    msg_out = list(msg_in)     # copy of message
    # find erasures/errors (ie: characters that were either replaced by null byte or changed to another character)
    erase_pos = []
    for i in range(0, len(msg_out)):
        if msg_out[i] < 0:
            msg_out[i] = 0
            erase_pos.append(i)
    if len(erase_pos) > nsym:
        raise ReedSolomonError("Too many erasures to correct")
    synd = rs_calc_syndromes(msg_out, nsym, fcr)
    if max(synd) == 0:
        return msg_out[:-nsym], msg_out[-nsym:]  # no errors
    fsynd = rs_forney_syndromes(synd, erase_pos, len(msg_out))
    err_poly = rs_gen_error_poly(fsynd)
    err_pos = rs_find_errors(err_poly, len(msg_out))
    if err_pos is None:
        raise ReedSolomonError("Could not locate error")
    msg_out = rs_correct_errata(msg_out, synd, erase_pos + err_pos, fcr)
    synd = rs_calc_syndromes(msg_out, nsym, fcr)
    if max(synd) > 0:
        raise ReedSolomonError("Could not correct message")
    return msg_out[:-nsym], msg_out[-nsym:] # also return the corrected ecc block so that the user can check()

def rs_correct_msg_base3(msg_in, nsym):
    if len(msg_in) > 255:
        raise ValueError("message too long")
    msg_out = list(msg_in)     # copy of message
    # find erasures/errors (ie: characters that were either replaced by null byte or changed to another character)
    erase_pos = []
    for i in range(0, len(msg_out)):
        if msg_out[i] < 0:
            msg_out[i] = 0
            erase_pos.append(i)
    if len(erase_pos) > nsym:
        raise ReedSolomonError("Too many erasures to correct")
    synd = rs_calc_syndromes_base3(msg_out, nsym, fcr=0)
    if max(synd) == 0:
        return msg_out[:-nsym], msg_out[-nsym:]  # no errors
    fsynd = rs_forney_syndromes(synd, erase_pos, len(msg_out))
    err_poly = rs_gen_error_poly(fsynd)
    err_pos = rs_find_errors_base3(err_poly)
    if err_pos is None:
        raise ReedSolomonError("Could not locate error")
    msg_out = rs_correct_errata(nsym, msg_out, synd, erase_pos + err_pos)
    synd = rs_calc_syndromes(msg_out, nsym, fcr=0)
    if max(synd) > 0:
        raise ReedSolomonError("Could not correct message")
    return msg_out[:-nsym], msg_out[-nsym:] # also return the corrected ecc block so that the user can check()

def rs_check(msg, nsym, fcr=0):
    '''Returns true if the message + ecc has no error of false otherwise'''
    return (max(rs_calc_syndromes(msg, nsym, fcr)) == 0)

def rs_check_base3(msg, nsym, fcr=0):
    '''Returns true if the message + ecc has no error of false otherwise'''
    return (max(rs_calc_syndromes_base3(msg, nsym, fcr)) == 0)


#===================================================================================================
# API
#===================================================================================================
class RSCodec(object):
    """
    A Reed Solomon encoder/decoder. After initializing the object, use ``encode`` to encode a
    (byte)string to include the RS correction code, and pass such an encoded (byte)string to
    ``decode`` to extract the original message (if the number of errors allows for correct decoding).
    The ``nsym`` argument is the length of the correction code, and it determines the number of
    error bytes (if I understand this correctly, half of ``nsym`` is correctable)
    """
    """
    Modifications by rotorgit 2/3/2015:
    Added support for US FAA ADSB UAT RS FEC, by allowing user to specify
    different primitive polynomial and non-zero first consecutive root (fcr).
    For UAT/ADSB use, set fcr=120 and prim=0x187 when instantiating
    the class; leaving them out will default for previous values (0 and
    0x11d)
    """
    def __init__(self, nsym=10, nsize=255, fcr=0, prim=0x11d):
        self.nsize = nsize
        self.nsym = nsym
        self.fcr = fcr
        self.prim = prim
        init_tables(prim)

    def encode(self, data):
        if isinstance(data, str):
            data = bytearray(data, "latin-1")
        chunk_size = self.nsize - self.nsym
        enc = bytearray()
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size]
            enc.extend(rs_encode_msg(chunk, self.nsym, fcr=self.fcr))
        return enc

    def decode(self, data):
        if isinstance(data, str):
            data = bytearray(data, "latin-1")
        dec = bytearray()
        for i in range(0, len(data), self.nsize):
            chunk = data[i:i+self.nsize]
            dec.extend(rs_correct_msg(chunk, self.nsym, fcr=self.fcr)[0])
        return dec

