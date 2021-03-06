"""
Customisable progressbar decorator for iterators.
Includes a default (x)range iterator printing to stderr.

Usage:
  from tqdm import trange[, tqdm]
  for i in trange(10):
    ...
"""
from __future__ import division, absolute_import # future division is important to divide integers and get as a result precise floating numbers (instead of truncated int)
from ._utils import _supports_unicode, _environ_cols, _range, _unich
import sys
import time


__author__ = {"github.com/": ["noamraph", "JackMc", "arkottke", "obiwanus",
                              "fordhurley", "kmike", "hadim", "casperdcl"]}
__all__ = ['tqdm', 'trange', 'format_interval', 'format_meter']

def format_sizeof(num, suffix='bytes'):
    '''Readable size format, courtesy of Sridhar Ratnakumar'''
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1000.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1000.0
    return "%.1f%s%s" % (num, 'Y', suffix)

def format_interval(t):
    mins, s = divmod(int(t), 60)
    h, m = divmod(mins, 60)
    if h:
        return '{0:d}:{1:02d}:{2:02d}'.format(h, m, s)
    else:
        return '{0:02d}:{1:02d}'.format(m, s)


def format_meter(n, total, elapsed, ncols=None, prefix='', unit=None, unit_format=False, ascii=False):
    """
    Return a string-based progress bar given some parameters

    Parameters
    ----------
    n  : int
        Number of finished iterations
    total  : int
        The expected total number of iterations. If None, only basic progress
        statistics are displayed (no ETA).
    elapsed  : float
        Number of seconds passed since start
    ncols  : int, optional
        The width of the entire output message. If sepcified, dynamically
        resizes the progress meter [default: None]. The fallback meter
        width is 10.
    prefix  : str, optional
        Prefix message (included in total width)
    ascii  : bool, optional
        If not set, use unicode (smooth blocks) to fill the meter
        [default: False]. The fallback is to use ASCII characters (1-9 #).

    Returns
    -------
    out  : Formatted meter and stats, ready to display.
    """
    if total and n > total: # in case the total is wrong (n is above the total), then we switch to the mode without showing the total prediction (since ETA would be wrong anyway)
        total = None

    elapsed_str = format_interval(elapsed)
    if elapsed:
        if unit_format:
            rate = format_sizeof(n / elapsed, suffix='')
        else:
            rate = '{0:5.2f}'.format(n / elapsed)
    else:
        rate = '?'

    rate_unit = unit if unit else 'iters'
    if not unit: unit = ''

    n_fmt = str(n)
    total_fmt = str(total)
    if unit_format:
        n_fmt = format_sizeof(n, suffix='')
        if total: total_fmt = format_sizeof(total, suffix='')

    if total:
        frac = n / total
        percentage = '%3d%%' % (frac * 100)
        
        left_str = format_interval(elapsed * (total-n) / n) if n else '?'

        l_bar = '{1}{0:.0f}%|'.format(frac * 100, prefix) if prefix else \
                '{0:3.0f}%|'.format(frac * 100)
        r_bar = '| {0}/{1} [{2}<{3}, {4} it/s]'.format(
                n, total, elapsed_str, left_str, rate)

        N_BARS = max(1, ncols - len(l_bar) - len(r_bar)) if ncols else 10

        if ascii:
            bar_length, frac_bar_length = divmod(int(frac * N_BARS * 10), 10)

            bar = '#'*bar_length
            frac_bar = chr(48 + frac_bar_length) if frac_bar_length else ' '

        else:
            bar_length, frac_bar_length = divmod(int(frac * N_BARS * 8), 8)

            bar = _unich(0x2588)*bar_length
            frac_bar = _unich(0x2590 - frac_bar_length) \
                if frac_bar_length else ' '

        if bar_length < N_BARS:
            full_bar = l_bar + bar + frac_bar + \
                ' '*max(N_BARS - bar_length - 1, 0) + r_bar
        else:
            full_bar = l_bar + bar + r_bar

        return '%s%s%s %s/%s %s %s [elapsed:%s left:%s, %s %s/sec]' % (
            full_bar, n_fmt, total_fmt, unit, percentage, elapsed_str, left_str, rate, rate_unit)

    else:
        return '%s %s [elapsed:%s, %s %s/sec]' % (n_fmt, unit, elapsed_str, rate, rate_unit)


class StatusPrinter(object):
    """
    Manage the printing and in-place updating of a line of characters.
    Note that if the string is longer than a line, then in-place updating may not work (it will print a new line at each refresh).
    """
    def __init__(self, file):
        self.file = file
        self.last_printed_len = 0

    def print_status(self, s):
        self.file.write('\r'+s+' '*max(self.last_printed_len-len(s), 0))
        self.file.flush()
        self.last_printed_len = len(s)


class tqdm(object):
    """
    Decorate an iterable object, returning an iterator which acts exactly
    like the orignal iterable, but prints a dynamically updating
    progressbar every time a value is requested.

    Parameters
    ----------
    iterable  : iterable
        Iterable to decorate with a progressbar.
    desc  : str, optional
        Prefix for the progressbar.
    total  : int, optional
        The number of expected iterations. If not given, len(iterable) is
        used if possible. As a last resort, only basic progress statistics
        are displayed (no ETA, no progressbar).
    file  : `io.TextIOWrapper` or `io.StringIO`, optional
        Specifies where to output the progress messages.
        Uses file.write(str) and file.flush() methods.
    leave  : bool, optional
        if unset, removes all traces of the progressbar upon termination of
        iteration [default: False].
    ncols  : int, optional
        The width of the entire output message. If sepcified, dynamically
        resizes the progress meter [default: None]. The fallback meter
        width is 10.
    mininterval  : float, optional
        Minimum progress update interval, in seconds [default: 0.1].
    miniters  : int, optional
        Minimum progress update interval, in iterations [default: None].
    ascii  : bool, optional
        If not set, use unicode (smooth blocks) to fill the meter
        [default: False]. The fallback is to use ASCII characters (1-9 #).
    disable : bool
        Disable the progress bar if True [default: False].

    Returns
    -------
    out  : decorated iterator.
    """

    def __init__(self, iterable=None, desc=None, total=None, leave=False, file=sys.stderr,
         ncols=None, mininterval=0.1, miniters=None, unit=None, unit_format=False,
         ascii=None, disable=False):

        # Preprocess the arguments
        if total is None and iterable is not None:
            try:
                total = len(iterable)
            except (TypeError, AttributeError):
                total = None

        if (ncols is None) and (file in (sys.stderr, sys.stdout)):
            ncols = _environ_cols(file)

        if miniters is None:
            miniters = 0
            dynamic_miniters = True
        else:
            dynamic_miniters = False

        if ascii is None:
            ascii = not _supports_unicode(file)

        # Store the arguments
        self.iterable = iterable
        self.total = total
        self.prefix = desc+': ' if desc else ''
        self.leave = leave
        self.file = file
        self.ncols = ncols
        self.mininterval = mininterval
        self.miniters = miniters
        self.dynamic_miniters = dynamic_miniters
        self.unit = unit
        self.unit_format = unit_format
        self.ascii = ascii
        self.disable = disable

        # Initialize the screen printer
        self.sp = StatusPrinter(self.file)
        if not disable: self.sp.print_status(format_meter(0, total, 0, ncols, prefix, unit, unit_format, ascii))

        # Init the time/iterations counters
        self.start_t = self.last_print_t = time.time()
        self.last_print_n = 0
        self.n = 0

    def __iter__(self):
        ''' For backward-compatibility to use: for x in tqdm(iterable) '''
        if self.disable: # if the bar is disabled, then just walk the iterable (note that we keep this condition above the loop for performance, so that we don't have to repeatedly check the condition inside the loop)
            for obj in self.iterable:
                yield obj
        else:
            for obj in self.iterable:
                yield obj
                # Now the object was created and processed, so we can print the meter.
                self.update(1)
            self.close()

    def update(self, n=1):
        """
        Manually update the progress bar, useful for streams such as reading files (set init(total=filesize) and then in the reading loop, use update(len(current_buffer)) )

        Parameters
        ----------
        n  : int
            Increment to add to the internal counter of iterations.
        """
        if n < 1:
            n = 1
        self.n += n

        delta_it = self.n - self.last_print_n
        if delta >= self.miniters:
            # We check the counter first, to reduce the overhead of time.time()
            cur_t = time.time()
            if cur_t - self.last_print_t >= self.mininterval:
                self.sp.print_status(format_meter(self.n, self.total, cur_t-self.start_t, self.ncols, self.prefix, self.unit, self.unit_format, self.ascii))
                if self.dynamic_miniters: self.miniters = max(self.miniters, delta_it)
                self.last_print_n = self.n
                self.last_print_t = cur_t

    def close(self):
        """
        Call this method to force print the last progress bar update based on the latest n value
        """
        if self.leave:
            if self.last_print_n < self.n:
                cur_t = time.time()
                self.sp.print_status(format_meter(self.n, self.total, cur_t-self.start_t, self.ncols, self.prefix, self.unit, self.unit_format, self.ascii))
            self.file.write('\n')
        else:
            self.sp.print_status('')
            self.file.write('\r')


def trange(*args, **kwargs):
    """
    A shortcut for tqdm(xrange(*args), **kwargs).
    On Python3+ range is used instead of xrange.
    """
    return tqdm(_range(*args), **kwargs)
