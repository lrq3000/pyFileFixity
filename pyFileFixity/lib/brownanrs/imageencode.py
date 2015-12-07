from PIL import Image
import sys

from . import rs

rowstride = 255

def encode(input, output_filename):
    """Encodes the input data with reed-solomon error correction in 223 byte
    blocks, and outputs each block along with 32 parity bytes to a new file by
    the given filename.

    input is a file-like object

    The outputted image will be in png format, and will be 255 by x pixels with
    one color channel. X is the number of 255 byte blocks from the input. Each
    block of data will be one row, therefore, the data can be recovered if no
    more than 16 pixels per row are altered.
    """
    coder = rs.RSCoder(255,223)

    output = []

    while True:
        block = input.read(223)
        if not block: break
        code = coder.encode_fast(block)
        output.append(code)
        sys.stderr.write(".")

    sys.stderr.write("\n")

    out = Image.new("L", (rowstride,len(output)))
    out.putdata("".join(output))
    out.save(output_filename)

def decode(input_filename):
    coder = rs.RSCoder(255,223)
    input = Image.open(input_filename)
    data = "".join(chr(x) for x in input.getdata())
    del input

    blocknum = 0
    while True:
        if blocknum*255 > len(data):
            break
        rowdata = data[blocknum*255:(blocknum+1)*255]
        if not rowdata: break

        decoded = coder.decode_fast(rowdata)

        blocknum += 1
        sys.stdout.write(str(decoded))
        sys.stderr.write(".")
    sys.stderr.write("\n")

if __name__ == "__main__":

    if "-d" == sys.argv[1]:
        # decode
        decode(sys.argv[2])

    else:
        # encode
        if len(sys.argv) >= 2:
            encode(open(sys.argv[1], 'rb'), sys.argv[2])
        else:
            encode(sys.stdin, sys.argv[1])
