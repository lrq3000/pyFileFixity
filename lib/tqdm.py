__all__ = ['tqdm', 'trange']

import sys
import time

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
        return '%d:%02d:%02d' % (h, m, s)
    else:
        return '%02d:%02d' % (m, s)


def format_meter(n, total, elapsed, unit=None, unit_format=False):
''' Return a string-based progress bar given some parameters '''
    # n - number of finished iterations
    # total - total number of iterations, or None
    # elapsed - number of seconds passed since start
    if n > total: # in case the total is wrong (n is above the total), then we switch to the mode without showing the total prediction (since ETA would be wrong anyway)
        total = None

    elapsed_str = format_interval(elapsed)
    if elapsed:
        if unit_format:
            rate = format_sizeof(n / elapsed, suffix='')
        else:
            rate = '%5.2f' % (n / elapsed)
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
        frac = float(n) / total

        N_BARS = 10
        bar_length = int(frac*N_BARS)
        bar = '#'*bar_length + '-'*(N_BARS-bar_length)

        percentage = '%3d%%' % (frac * 100)

        left_str = format_interval(elapsed / n * (total-n)) if n else '?'

        return '|%s| %s/%s %s %s [elapsed:%s left:%s, %s %s/sec]' % (
            bar, n_fmt, total_fmt, unit, percentage, elapsed_str, left_str, rate, rate_unit)

    else:
        return '%s %s [elapsed:%s, %s %s/sec]' % (n_fmt, unit, elapsed_str, rate, rate_unit)


class StatusPrinter(object):
    ''' Manage the printing and in-place updating of a line of characters.
    Note that if the string is longer than a line, then in-place updating may not work (it will print a new line at each refresh). '''
    def __init__(self, file):
        self.file = file
        self.last_printed_len = 0

    def print_status(self, s):
        self.file.write('\r'+s+' '*max(self.last_printed_len-len(s), 0))
        self.file.flush()
        self.last_printed_len = len(s)


class tqdm:
    ''' Get an iterable object, and return an iterator which acts exactly like the
    iterable, but prints a progress meter and updates it every time a value is
    requested.
    'desc' can contain a short string, describing the progress, that is added
    in the beginning of the line.
    'total' can give the number of expected iterations. If not given,
    len(iterable) is used if it is defined.
    'file' can be a file-like object to output the progress message to.
    If leave is False, tqdm deletes its traces from screen after it has
    finished iterating over all elements.
    If less than mininterval seconds or miniters iterations have passed since
    the last progress meter update, it is not updated again.
    '''

    def __init__(self, iterable=None, desc='', total=None, leave=False, file=sys.stderr,
         mininterval=0.5, miniters=1, unit=None, unit_format=False):

        self.iterable = iterable

        if total is None and iterable is not None:
            try:
                total = len(iterable)
            except TypeError:
                total = None
        self.total = total

        self.prefix = desc+': ' if desc else ''
        self.leave = leave
        self.file = file
        self.mininterval = mininterval
        self.miniters = miniters
        self.unit = unit
        self.unit_format = unit_format

        self.sp = StatusPrinter(self.file)
        self.sp.print_status(self.prefix + format_meter(0, self.total, 0, unit=self.unit, unit_format=self.unit_format))

        self.start_t = self.last_print_t = time.time()
        self.last_print_n = 0
        self.n = 0

    def __iter__(self):
    ''' For backward-compatibility to use: for x in tqdm(iterable) '''
        for obj in self.iterable:
            yield obj
            # Now the object was created and processed, so we can print the meter.
            self.n += 1
            if self.n - self.last_print_n >= self.miniters:
                # We check the counter first, to reduce the overhead of time.time()
                cur_t = time.time()
                if cur_t - self.last_print_t >= self.mininterval:
                    self.sp.print_status(self.prefix + format_meter(self.n, self.total, cur_t-self.start_t, unit=self.unit, unit_format=self.unit_format))
                    self.last_print_n = self.n
                    self.last_print_t = cur_t
        self.close()

    def close(self):
    ''' Call this method to force print the last progress bar update based on the latest n value '''
        if not self.leave:
            self.sp.print_status('')
            self.file.write('\r')
        else:
            if self.last_print_n < self.n:
                cur_t = time.time()
                self.sp.print_status(self.prefix + format_meter(self.n, self.total, cur_t-self.start_t, unit=self.unit, unit_format=self.unit_format))
            self.file.write('\n')

    def update(self, n=1):
    ''' To manually update the progress bar, useful for streams such as reading files (set init(total=filesize) and then in the reading loop, use update(len(current_buffer)) ) '''
        if n < 1:
            n = 1
        self.n += n

        if self.n - self.last_print_n >= self.miniters:
            # We check the counter first, to reduce the overhead of time.time()
            cur_t = time.time()
            if cur_t - self.last_print_t >= self.mininterval:
                self.sp.print_status(self.prefix + format_meter(self.n, self.total, cur_t-self.start_t, unit=self.unit, unit_format=self.unit_format))
                self.last_print_n = self.n
                self.last_print_t = cur_t


def trange(*args, **kwargs):
    ''' A shortcut for writing tqdm(range()) on py3 or tqdm(xrange()) on py2 '''
    try:
        f = xrange
    except NameError:
        f = range

    return tqdm(f(*args), **kwargs)
