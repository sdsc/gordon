#!/usr/bin/env python

import numpy
import pylab

def plot_timing(timing, image_name):
    pylab.plot(timing[:,0], timing[:,1])
    pylab.xlabel('GiB')
    pylab.ylabel('seconds')
    pylab.savefig(image_name)

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print "Usage: plot_grow_mem.py <grow-mem output>"
        sys.exit(-1)
    elif len(sys.argv) == 3:
        image_name = sys.argv[2]
    else:
        image_name = 'grow-mem-timing.png'

    mem_timing = numpy.loadtxt(sys.argv[1], usecols=(1,3))
    plot_timing(mem_timing, image_name)

    sys.exit(0)
